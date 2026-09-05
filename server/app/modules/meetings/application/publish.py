"""The summarize-and-persist flow, run once per meeting — by the API
layer's background task (a later phase) right after `IngestMixin.
ingest_meeting` returns. Runs detached from any request: nothing here
raises back to a caller: a missing meeting or a summarization failure is
logged and/or recorded on the row instead.
"""

from __future__ import annotations

import logging
from dataclasses import asdict
from typing import Any
from uuid import UUID

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.domain.meeting_record import MeetingRecord
from app.modules.meetings.domain.rendering import render_summary_text
from app.modules.meetings.domain.roles import MeetingRole

logger = logging.getLogger(__name__)


class PublishMixin(ServiceBase):
    async def summarize_and_publish(self, meeting_id: UUID) -> None:
        meeting = await self._meetings_repository.get_by_id(meeting_id)
        if meeting is None:
            # Nothing to report to — this runs detached from any request.
            logger.warning("summarize_and_publish_meeting_not_found meeting_id=%s", meeting_id)
            return

        companies = self._reconstruct_companies(
            counterparty_role=meeting.counterparty_role,
            org_id=meeting.org_id,
            org_name_raw=meeting.org_name_raw,
            metadata=meeting.metadata,
        )

        try:
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
        metadata: dict[str, Any],
    ) -> dict[MeetingRole, str]:
        """Best-effort reconstruction of the original 5-role {role: name}
        mapping from what `IngestMixin` persisted — used only for prompt
        framing (title bracket, role attribution, deal_momentum
        applicability), never for persistence. `primary_role`/`other_side`
        are the metadata keys `IngestMixin.ingest_meeting` writes; keep
        this in sync with that shape.
        """
        companies: dict[MeetingRole, str] = {}

        primary_role_value = (metadata or {}).get("primary_role")
        primary_role = (
            MeetingRole(primary_role_value)
            if primary_role_value
            else (MeetingRole(counterparty_role) if counterparty_role else None)
        )
        if primary_role is not None:
            name = org_name_raw or org_id
            if name:
                companies[primary_role] = name

        for entry in (metadata or {}).get("other_side") or []:
            role = MeetingRole(entry["role"])
            name = entry.get("org_name_raw") or entry.get("org_id")
            if name:
                companies[role] = name

        return companies
