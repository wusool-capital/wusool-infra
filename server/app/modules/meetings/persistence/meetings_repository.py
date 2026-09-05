"""Read/write access to the shared `meetings` table for the desktop-push
flow (dedupe check, create, completion/failure bookkeeping, stalled-summary
recovery, sync-status listing). `add()`/`flush()`/`execute()` only — never
`commit()`/`rollback()`; the caller owns the transaction boundary.

Implements `application.ports.meetings.MeetingsRepositoryPort`.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meeting
from app.modules.meetings.domain.meeting_record import MeetingRecord, MeetingSyncStatus


class MeetingsRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_install_and_recording(
        self, install_id: str, local_recording_id: str
    ) -> MeetingRecord | None:
        stmt = select(Meeting).where(
            Meeting.install_id == install_id, Meeting.local_recording_id == local_recording_id
        )
        meeting = (await self._session.execute(stmt)).scalar_one_or_none()
        return self._to_record(meeting) if meeting is not None else None

    async def create(
        self,
        *,
        id: UUID,
        org_id: str | None,
        org_name_raw: str | None,
        counterparty_role: str | None,
        meeting_type: str | None,
        occurred_at: datetime,
        title: str | None,
        source: str = "in_house",
        duration_s: int | None,
        transcript: str | None,
        install_id: str | None,
        local_recording_id: str | None,
        status: str = "summarizing",
        metadata_: dict[str, Any] | None = None,
    ) -> MeetingRecord:
        meeting = Meeting(
            id=id,
            org_id=org_id,
            org_name_raw=org_name_raw,
            counterparty_role=counterparty_role,
            meeting_type=meeting_type,
            occurred_at=occurred_at,
            title=title,
            source=source,
            duration_s=duration_s,
            transcript=transcript,
            install_id=install_id,
            local_recording_id=local_recording_id,
            status=status,
            metadata_=metadata_ or {},
        )
        self._session.add(meeting)
        await self._session.flush()
        return self._to_record(meeting)

    async def mark_completed(
        self,
        meeting_id: UUID,
        *,
        summary_text: str,
        summary_json: dict[str, Any],
        title: str | None,
    ) -> None:
        values: dict[str, Any] = {
            "status": "completed",
            "summary": summary_text,
            "summary_json": summary_json,
        }
        if title is not None:
            values["title"] = title
        await self._session.execute(
            update(Meeting).where(Meeting.id == meeting_id).values(**values)
        )

    async def mark_failed(self, meeting_id: UUID, *, reason: str) -> None:
        meeting = await self._session.get(Meeting, meeting_id)
        if meeting is None:
            return
        metadata = {**meeting.metadata_, "failure_reason": reason}
        await self._session.execute(
            update(Meeting)
            .where(Meeting.id == meeting_id)
            .values(status="failed", metadata_=metadata)
        )

    async def recover_stalled(self, meeting_id: UUID, *, cutoff: datetime) -> bool:
        """Conditional UPDATE that doubles as the concurrency lock: only the
        caller whose UPDATE actually matches a row (still `summarizing` and
        stalled since before `cutoff`) gets `True` back — two simultaneous
        callers for the same meeting can never both win.
        """
        stmt = (
            update(Meeting)
            .where(
                Meeting.id == meeting_id,
                Meeting.status == "summarizing",
                Meeting.summary_started_at < cutoff,
            )
            .values(summary_started_at=func.now())
            .returning(Meeting.id)
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none() is not None

    async def get_by_id(self, meeting_id: UUID) -> MeetingRecord | None:
        meeting = await self._session.get(Meeting, meeting_id)
        return self._to_record(meeting) if meeting is not None else None

    async def list_by_install_id(self, install_id: str, *, limit: int) -> list[MeetingSyncStatus]:
        """Column-scoped select — never loads full `Meeting` rows (with their
        transcript/summary columns) for what is just a sync-status listing.
        """
        stmt = (
            select(
                Meeting.id,
                Meeting.local_recording_id,
                Meeting.status,
                Meeting.summary_json.is_not(None).label("summary_available"),
            )
            .where(Meeting.install_id == install_id)
            .order_by(Meeting.created_at.desc())
            .limit(limit)
        )
        rows = (await self._session.execute(stmt)).all()
        return [
            MeetingSyncStatus(
                id=row.id,
                local_recording_id=row.local_recording_id,
                status=row.status,
                summary_available=row.summary_available,
            )
            for row in rows
        ]

    def _to_record(self, meeting: Meeting) -> MeetingRecord:
        return MeetingRecord(
            id=meeting.id,
            org_id=meeting.org_id,
            org_name_raw=meeting.org_name_raw,
            counterparty_role=meeting.counterparty_role,
            meeting_type=meeting.meeting_type,
            occurred_at=meeting.occurred_at,
            title=meeting.title,
            source=meeting.source,
            audio_ref=meeting.audio_ref,
            duration_s=meeting.duration_s,
            created_by_ref=meeting.created_by_ref,
            participants=meeting.participants,
            transcript=meeting.transcript,
            summary=meeting.summary,
            metadata=meeting.metadata_,
            created_at=meeting.created_at,
            scribe_meeting_id=meeting.scribe_meeting_id,
            status=meeting.status,
            install_id=meeting.install_id,
            local_recording_id=meeting.local_recording_id,
            summary_json=meeting.summary_json,
            summary_started_at=meeting.summary_started_at,
        )
