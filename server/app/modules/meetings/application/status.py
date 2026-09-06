"""Read paths for the desktop sync flow: fetching one meeting's status,
and listing recent meetings for an install. Also owns stalled-meeting
recovery for the single-meeting path (see `_recover_if_stalled`'s
docstring for the scope tradeoff).
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.application.errors import MeetingNotFoundError
from app.modules.meetings.domain.meeting_record import MeetingRecord, MeetingSyncStatus

# TODO: promote to a Settings field if a real deployment needs this tuned;
# a local constant is fine for this phase.
_STALL_TIMEOUT = timedelta(minutes=10)


class StatusMixin(ServiceBase):
    async def get_status(self, meeting_id: UUID) -> tuple[MeetingRecord, bool]:
        """Returns (meeting, needs_resummarization). `needs_resummarization`
        is True when this call itself just recovered a stalled
        `summarizing` row (summary_started_at older than the stall
        cutoff) — the API layer must, in that case, schedule a fresh
        `PublishMixin.summarize_and_publish(meeting_id)` background task,
        since this method only flips the row back to a retryable state
        and never runs the LLM call itself.
        """
        meeting = await self._meetings_repository.get_by_id(meeting_id)
        if meeting is None:
            raise MeetingNotFoundError(f"Meeting {meeting_id} not found")

        needs_resummarization = await self._recover_if_stalled(meeting_id)
        if needs_resummarization:
            meeting = await self._meetings_repository.get_by_id(meeting_id)
            assert meeting is not None  # row we just recovered can't vanish mid-call

        return meeting, needs_resummarization

    async def list_for_install(self, install_id: str, *, limit: int) -> list[MeetingSyncStatus]:
        """Cheap polling listing — deliberately does NOT run stalled-
        recovery here: `list_by_install_id` only returns the narrow
        `MeetingSyncStatus` projection (no `summary_started_at`), so
        recovering per-row would need an extra fetch per meeting in this
        list. The desktop's sync sweep uses this for cheap polling and
        `get_status` for the actual per-meeting fetch, so recovering on
        `get_status` alone is judged sufficient coverage for this phase.
        """
        return await self._meetings_repository.list_by_install_id(install_id, limit=limit)

    async def _recover_if_stalled(self, meeting_id: UUID) -> bool:
        """Attempts to recover exactly one meeting_id if it's stalled in
        `summarizing` past the cutoff. Returns True only if this call won
        the recovery race (`recover_stalled` is expected to be an atomic,
        idempotent flip so concurrent callers don't both re-trigger
        summarization for the same meeting).
        """
        cutoff = datetime.now(UTC) - _STALL_TIMEOUT
        return await self._meetings_repository.recover_stalled(meeting_id, cutoff=cutoff)
