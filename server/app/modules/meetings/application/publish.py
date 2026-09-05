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
        # gets its full transcript+summary persisted. Only the CRM side
        # write below (notes table, optionally Attio) is gated on org_id.
        rendered = render_summary_text(summary)
        await self._meetings_repository.mark_completed(
            meeting_id,
            summary_text=rendered,
            summary_json=asdict(summary),
            title=summary.title,
        )

        org_id = meeting.org_id
        if org_id is None:
            # An unanchored note is unreadable in Attio and unqueryable in
            # Postgres — skip entirely rather than write a dangling row.
            # This meeting's summary is still fully available above; it
            # just has nowhere to file a CRM note without a company.
            return

        await self._write_note(org_id=org_id, content=rendered, meeting=meeting)

    async def _write_note(self, *, org_id: str, content: str, meeting: MeetingRecord) -> None:
        """Best-effort side write — never lets a note-writer/notes-
        repository failure roll back the meeting row's mark_completed
        above, which has already succeeded.
        """
        note_id: UUID | None = None
        if self._note_writer is not None and self._attio_note_object_slug:
            try:
                note_id = await self._note_writer.push_note(
                    organization_attio_id=org_id,
                    content=content,
                    created_at=meeting.occurred_at,
                    object_slug=self._attio_note_object_slug,
                )
            except Exception as exc:  # noqa: BLE001 - best-effort, must not affect the meeting
                logger.warning(
                    "note_push_failed meeting_id=%s error=%s",
                    meeting.id,
                    exc,
                    extra={"meeting_id": str(meeting.id), "error": str(exc)},
                )
                note_id = None

        try:
            await self._notes_repository.create(
                note_id=note_id,
                organization_id=org_id,
                note_type="Meeting",
                content=content,
            )
        except Exception as exc:  # noqa: BLE001 - meeting already succeeded, don't propagate
            logger.warning(
                "note_create_failed meeting_id=%s error=%s",
                meeting.id,
                exc,
                extra={"meeting_id": str(meeting.id), "error": str(exc)},
            )

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
