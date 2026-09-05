"""Ported from Scribe's `app.desktop.service.commands.
DesktopIngestMeetingCommand` — creates a `meetings` row from an
already-transcribed desktop push and leaves it `status="summarizing"`,
ready for a background summarization call.

Unlike Scribe, there is no local `companies` table here: a role selection
resolves either to a real Attio organization (`organization_lookup`) or to
a raw, unassociated name — this module never creates an organization.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.application.errors import (
    MeetingAlreadyExistsError,
    UnknownCompanyReferenceError,
)
from app.modules.meetings.domain.meeting_record import MeetingRecord
from app.modules.meetings.domain.rendering import TranscriptTurn, render_transcript_text
from app.modules.meetings.domain.roles import (
    MeetingRole,
    RoleTag,
    counterparty_role_column,
    encode_role_metadata,
    meeting_type_column,
    other_roles,
    select_primary_role,
)

# Sentinel selection value meaning "create a new company with the typed
# name" rather than reusing a matched candidate — same encoding as Scribe's
# `app.companies.service.confirm.CREATE_NEW_VALUE`. This module never
# actually creates an organization for it (no local `companies` table to
# create it in); it just carries the typed name through as org_name_raw.
_CREATE_NEW_VALUE = "__create_new__"
_ATTIO_VALUE_PREFIX = "attio:"


class _ResolvedRole:
    __slots__ = ("org_id", "org_name_raw")

    def __init__(self, org_id: str | None, org_name_raw: str | None) -> None:
        self.org_id = org_id
        self.org_name_raw = org_name_raw


class IngestMixin(ServiceBase):
    async def ingest_meeting(
        self,
        *,
        install_id: str,
        local_recording_id: str,
        transcript: list[TranscriptTurn],
        duration_seconds: float,
        role_selections: dict[MeetingRole, str],
        role_queries: dict[MeetingRole, str],
    ) -> MeetingRecord:
        """Create the `meetings` row for a desktop-pushed transcript.

        Ends at "row created, status=summarizing, ready for a background
        summarization call" — it deliberately does NOT call
        `summarization_service`/`PublishMixin.summarize_and_publish`
        itself. The API layer (a later phase) is responsible for
        scheduling `summarize_and_publish(meeting.id)` as a background
        task right after this returns, so a slow/failing LLM call never
        blocks the desktop push's HTTP response.
        """
        existing = await self._meetings_repository.get_by_install_and_recording(
            install_id, local_recording_id
        )
        if existing is not None:
            # Push is one-shot per (install_id, local_recording_id): a
            # re-push after further local edits would otherwise silently
            # discard those edits, so this surfaces as a conflict instead.
            raise MeetingAlreadyExistsError(
                f"Meeting for install {install_id} / recording "
                f"{local_recording_id} was already pushed."
            )

        resolved: dict[MeetingRole, _ResolvedRole] = {}
        for role, selection in role_selections.items():
            result = await self._resolve_role_selection(selection, role_queries.get(role))
            if result is not None:
                resolved[role] = result

        # select_primary_role/other_roles only check presence in the dict,
        # so any resolved marker string works as the value.
        presence = {role: "resolved" for role in resolved}
        primary = select_primary_role(presence)
        other = other_roles(presence, primary)

        primary_resolved = resolved.get(primary) if primary is not None else None
        other_side = [
            RoleTag(
                role=role,
                org_id=resolved[role].org_id,
                org_name_raw=resolved[role].org_name_raw,
            )
            for role in other
        ]
        # `counterparty_role`/`meeting_type` only ever distinguish
        # seller/buyer/internal — an investor or general primary role is
        # otherwise indistinguishable from the other on those two columns
        # alone. Stashing it here too (via `encode_role_metadata` — read
        # back by `PublishMixin._reconstruct_companies` via its inverse,
        # `decode_role_metadata`; keep both call sites in sync through that
        # pair of functions rather than each hand-rolling the same dict
        # shape) is what lets PublishMixin reconstruct the original 5-role
        # mapping for prompt framing.
        metadata_: dict[str, object] | None = None
        if primary is not None or other_side:
            metadata_ = encode_role_metadata(primary=primary, other=other_side)

        # Rendered once, reused both as the stored transcript column and
        # (in PublishMixin) as the summarization prompt's input — never
        # re-derived from the typed turns a second time.
        transcript_text = render_transcript_text(transcript)
        occurred_at = datetime.now(UTC) - timedelta(seconds=duration_seconds)

        return await self._meetings_repository.create(
            id=uuid.uuid4(),
            org_id=primary_resolved.org_id if primary_resolved else None,
            org_name_raw=primary_resolved.org_name_raw if primary_resolved else None,
            counterparty_role=counterparty_role_column(primary),
            meeting_type=meeting_type_column(primary),
            occurred_at=occurred_at,
            title=None,
            source="in_house",
            duration_s=int(duration_seconds),
            transcript=transcript_text,
            install_id=install_id,
            local_recording_id=local_recording_id,
            status="summarizing",
            metadata_=metadata_,
        )

    async def _resolve_role_selection(
        self, selection: str | None, query: str | None
    ) -> _ResolvedRole | None:
        if selection is None:
            return None
        if selection == _CREATE_NEW_VALUE:
            return _ResolvedRole(org_id=None, org_name_raw=(query or "").strip() or None)
        if selection.startswith(_ATTIO_VALUE_PREFIX):
            attio_id = selection[len(_ATTIO_VALUE_PREFIX) :]
            org = await self._organization_lookup.get_by_id(attio_id)
            if org is not None:
                return _ResolvedRole(org_id=org.attio_id, org_name_raw=org.name)
            # Reference is well-formed but the lookup came back empty (org
            # deleted, or an Attio cache desync since the desktop app's own
            # search offered this candidate) — do NOT still trust the id:
            # `Meeting.org_id` is a real FK to `organizations.attio_id`,
            # and writing an id that doesn't exist there raises an
            # unhandled IntegrityError at flush, surfacing as a raw 500
            # instead of this push degrading gracefully. Fall back to
            # org_name_raw only, exactly like the free-text/create-new
            # case below.
            return _ResolvedRole(org_id=None, org_name_raw=(query or "").strip() or None)
        try:
            uuid.UUID(selection)
        except ValueError:
            # Bare free-text query, not a sentinel and not a UUID: treat
            # as an unassociated company name, exactly like __create_new__.
            return _ResolvedRole(org_id=None, org_name_raw=selection.strip() or None)
        # A Scribe-era desktop session may still hold a stale local
        # company UUID selection — this module has no `companies` table
        # to resolve it against.
        raise UnknownCompanyReferenceError(f"Unknown company reference: {selection!r}")
