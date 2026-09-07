"""The summarize-and-persist flow, run once per meeting — by the API
layer's background task (a later phase) right after `IngestMixin.
ingest_meeting` returns. Runs detached from any request: nothing here
raises back to a caller: a missing meeting or a summarization failure is
logged and/or recorded on the row instead.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from uuid import UUID

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.domain.meeting_record import MeetingRecord
from app.modules.meetings.domain.rendering import render_summary_text
from app.modules.meetings.domain.role_ref import ActiveRoleRef
from app.modules.meetings.domain.roles import MeetingRole, decode_role_metadata, try_role
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)

# Placeholder for a role that's genuinely tagged (present in
# counterparty_role/metadata) but was resolved with no organization name at
# all — see `_reconstruct_companies`.
_UNKNOWN_COMPANY_NAME = "(name not provided)"


class PublishMixin(ServiceBase):
    async def summarize_and_publish(self, meeting_id: UUID) -> None:
        meeting = await self._meetings_repository.get_by_id(meeting_id)
        if meeting is None:
            # Nothing to report to — this runs detached from any request.
            logger.warning("summarize_and_publish_meeting_not_found meeting_id=%s", meeting_id)
            return

        try:
            # `_reconstruct_companies` is inside this `try` too, not just
            # the summarize call — `decode_role_metadata` is defensive by
            # contract, but this method runs detached from any request
            # with no caller to hand an exception to, so anything before
            # `mark_failed` below must degrade to it rather than strand
            # the row in `summarizing` forever.
            companies = self._reconstruct_companies(
                counterparty_role=meeting.counterparty_role,
                org_id=meeting.org_id,
                org_name_raw=meeting.org_name_raw,
                metadata=meeting.metadata,
            )
            async with self._summary_semaphore:
                summary = await self._summarization_service.summarize(
                    meeting.transcript or "",
                    companies=companies,
                    meeting_date=meeting.occurred_at.date().isoformat(),
                )
        except Exception as exc:
            logger.warning(
                "summarize_and_publish_failed meeting_id=%s error=%s",
                meeting_id,
                exc,
                extra={"meeting_id": str(meeting_id), "error": str(exc)},
            )
            await self._meetings_repository.mark_failed(meeting_id, reason=str(exc))
            return

        # The meetings row itself is ALWAYS written here, org_id or not —
        # an internal/general meeting (no company tagged at all) still
        # gets its full transcript+summary persisted.
        rendered = render_summary_text(summary)
        await self._meetings_repository.mark_completed(
            meeting_id,
            summary_text=rendered,
            summary_json=asdict(summary),
            title=summary.title,
        )

        # Every meeting files a note now, org_id or not — an unanchored
        # note used to be skipped entirely ("unreadable in Attio and
        # unqueryable in Postgres"), but `notes.organization_id` was made
        # nullable specifically for this case (see migration
        # e0c1e7522181), and `primary_role` now gives an org-less note a
        # way to be found/filtered that didn't exist before.
        await self._write_note(org_id=meeting.org_id, content=rendered, meeting=meeting)

    async def _write_note(
        self, *, org_id: str | None, content: str, meeting: MeetingRecord
    ) -> None:
        """Best-effort side write — never lets a note-writer/notes-
        repository failure roll back the meeting row's mark_completed
        above, which has already succeeded.
        """
        primary = meeting.primary_role
        role_ref = await self._resolve_role(org_id=org_id, primary=primary)

        buyer_role_id: UUID | None = None
        seller_role_id: UUID | None = None
        buyer_role_entry_id: str | None = None
        seller_role_entry_id: str | None = None
        if role_ref is not None:
            # Skip the link entirely (both sides) when the row has no
            # `legacy_entry_id`: `ddl_commands`' inbound note sync
            # (`_NOTE_UPSERT`) always re-resolves `buyer_role_id`/
            # `seller_role_id` from whatever we send Attio, so sending a
            # Postgres uuid with nothing on the Attio side means the next
            # `note.updated`/`note.created` webhook for this note would
            # resolve NULL and silently overwrite the uuid we just wrote.
            # Keeping both sides agreeing on "no link" avoids that.
            if role_ref.legacy_entry_id is not None:
                if primary is MeetingRole.BUYER:
                    buyer_role_id = role_ref.id
                    buyer_role_entry_id = role_ref.legacy_entry_id
                elif primary is MeetingRole.SELLER:
                    seller_role_id = role_ref.id
                    seller_role_entry_id = role_ref.legacy_entry_id

        # No availability gate: the `note` object exists in SOURCE, which
        # serves both environments now. `push_note` swallows its own Attio
        # errors and returns None; the except here covers anything it cannot.
        note_attio_id: UUID | None = None
        try:
            note_attio_id = await self._note_writer.push_note(
                organization_attio_id=org_id,
                content=content,
                created_at=meeting.occurred_at,
                primary_role=primary.value if primary is not None else None,
                buyer_role_entry_id=buyer_role_entry_id,
                seller_role_entry_id=seller_role_entry_id,
            )
        except Exception as exc:  # noqa: BLE001 - best-effort, must not affect the meeting
            logger.warning(
                "note_push_failed meeting_id=%s error=%s",
                meeting.id,
                exc,
                extra={"meeting_id": str(meeting.id), "error": str(exc)},
            )
            note_attio_id = None

        try:
            note_id = await self._notes_repository.create(
                note_id=note_attio_id,
                organization_id=org_id,
                note_type="Meeting",
                content=content,
                primary_role=primary.value if primary is not None else None,
                buyer_role_id=buyer_role_id,
                seller_role_id=seller_role_id,
            )
        except Exception as exc:  # noqa: BLE001 - meeting already succeeded, don't propagate
            logger.warning(
                "note_create_failed meeting_id=%s error=%s",
                meeting.id,
                exc,
                extra={"meeting_id": str(meeting.id), "error": str(exc)},
            )
            return

        try:
            await self._meetings_repository.set_note_id(meeting.id, note_id=note_id)
        except Exception as exc:  # noqa: BLE001 - note already succeeded, don't propagate
            logger.warning(
                "note_id_writeback_failed meeting_id=%s error=%s",
                meeting.id,
                exc,
                extra={"meeting_id": str(meeting.id), "error": str(exc)},
            )

    async def _resolve_role(
        self, *, org_id: str | None, primary: MeetingRole | None
    ) -> ActiveRoleRef | None:
        """The one active buyer/seller-role row this note should link to,
        or `None` when there's nothing to link (no org, no buyer/seller
        primary role, or the org has no matching active role). Best-effort:
        a lookup failure degrades to `None` rather than blocking the note.
        """
        if org_id is None or primary not in (MeetingRole.BUYER, MeetingRole.SELLER):
            return None
        try:
            if primary is MeetingRole.BUYER:
                return await self._role_lookup.get_active_buyer_role(org_id)
            return await self._role_lookup.get_active_seller_role(org_id)
        except Exception as exc:  # noqa: BLE001 - best-effort, must not affect the meeting/note
            logger.warning(
                "role_lookup_failed org_id=%s error=%s",
                org_id,
                exc,
                extra={"org_id": org_id, "error": str(exc)},
            )
            return None

    @staticmethod
    def _reconstruct_companies(
        *,
        counterparty_role: str | None,
        org_id: str | None,
        org_name_raw: str | None,
        metadata: JsonObject,
    ) -> dict[MeetingRole, str]:
        """Best-effort reconstruction of the original 5-role {role: name}
        mapping from what `IngestMixin` persisted — used only for prompt
        framing (title bracket, role attribution, deal_momentum
        applicability), never for persistence. Decodes via
        `decode_role_metadata`, the inverse of `encode_role_metadata`
        (`IngestMixin.ingest_meeting`'s own encoder) — the two stay in sync
        through that shared pair of functions, not independent dict
        literals.
        """
        primary_role, other_side = decode_role_metadata(metadata)
        if primary_role is None and counterparty_role:
            # `counterparty_role` is DB-constrained to 'seller'/'buyer' by a
            # native Postgres enum, so this should always resolve — `try_role`
            # rather than `MeetingRole(...)` anyway, since "should always"
            # is not "cannot fail", and this whole function's contract is
            # never to raise.
            primary_role = try_role(counterparty_role)

        # A role can be tagged (present as counterparty_role/metadata) with
        # NO name at all — e.g. "create new organization" picked without
        # typing a name (`IngestMixin._resolve_role_selection`'s
        # _CREATE_NEW_VALUE branch allows org_name_raw=None). Dropping such
        # a role from `companies` when its name is empty would make
        # `momentum_applies`/the title-bracket logic treat a genuinely
        # tagged meeting as untagged — fall back to a placeholder instead
        # of skipping the role.
        companies: dict[MeetingRole, str] = {}
        if primary_role is not None:
            companies[primary_role] = org_name_raw or org_id or _UNKNOWN_COMPANY_NAME

        for tag in other_side:
            companies[tag.role] = tag.org_name_raw or tag.org_id or _UNKNOWN_COMPANY_NAME

        return companies
