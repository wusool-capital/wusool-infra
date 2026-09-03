"""Read-only access to the shared `meetings` table (§ meeting_note.py).
`add()`/`flush()`/`execute()` only — never `commit()`/`rollback()`; the
caller owns the transaction boundary.

Implements `application.ports.meetings.MeetingRepositoryPort`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Meeting
from app.modules.matching_engine.domain.meetings import MeetingNote


class MeetingRepository:
    def __init__(self, session: AsyncSession, *, max_chars: int) -> None:
        self._session = session
        self._max_chars = max_chars

    async def get_recent_by_org(self, org_attio_id: str) -> list[MeetingNote]:
        """All meeting notes for the org, ordered by occurred_at DESC, each
        truncated to `max_chars` with a visible marker. Returns [] for no
        rows or no match — never raises; meeting notes are optional context
        everywhere they're used. Total-budget selection (oldest +
        most-recent-until-budget-exhausted) is applied by the prompt-building
        step, not here, since it's a presentation concern.
        """
        stmt = (
            select(Meeting)
            .where(Meeting.org_id == org_attio_id, Meeting.summary.is_not(None))
            .order_by(Meeting.occurred_at.desc())
        )
        rows = (await self._session.execute(stmt)).scalars().all()
        return [self._to_note(row) for row in rows]

    def _to_note(self, row: Meeting) -> MeetingNote:
        summary = row.summary or ""
        truncated = len(summary) > self._max_chars
        if truncated:
            summary = summary[: self._max_chars] + "... [truncated]"
        return MeetingNote(
            occurred_at=row.occurred_at,
            title=row.title,
            summary=summary,
            truncated=truncated,
        )
