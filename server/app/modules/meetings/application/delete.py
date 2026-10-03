"""Delete flow for the desktop app's "remove from server & Attio" checkbox
(AZM-126). Soft-deletes only — `meetings.removed_at`/`notes.removed_at` —
never a hard DELETE (see the `removed_at` migration's own docstring for
why).

Idempotent: deleting an already-removed or never-existing meeting is a
successful no-op. The desktop app has no other identifier to retry with —
`(install_id, local_recording_id)` is the only key it ever gets back — so a
404 here would give it nothing useful to do differently on a retry.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.application.errors import MeetingStillProcessingError

# Mirrors `StatusMixin`'s own `_STALL_TIMEOUT` — a meeting whose
# summarization has been stuck this long is treated as abandoned, not
# actively being written to, so deleting it can't race the publish flow.
_STALL_TIMEOUT = timedelta(minutes=10)


class DeleteMixin(ServiceBase):
    async def delete_meeting(self, install_id: str, local_recording_id: str) -> None:
        meeting = await self._meetings_repository.get_by_install_and_recording(
            install_id, local_recording_id
        )
        if meeting is None or meeting.removed_at is not None:
            return  # already gone — idempotent success, see module docstring

        if meeting.status == "summarizing":
            cutoff = datetime.now(UTC) - _STALL_TIMEOUT
            stalled = meeting.summary_started_at is not None and meeting.summary_started_at < cutoff
            if not stalled:
                raise MeetingStillProcessingError(
                    f"Meeting {meeting.id} is still summarizing; retry shortly."
                )
            # Abandoned, not actively being written to — flip it out of
            # `summarizing` first so `soft_delete`'s own guard (which
            # refuses a row still `summarizing`) can proceed.
            await self._meetings_repository.mark_failed(
                meeting.id, reason="deleted from desktop while stalled"
            )

        # Attio before Postgres: if the Attio delete raises (anything but a
        # 404), nothing below runs. If a later Postgres write fails, Attio is
        # already gone, but every step is idempotent so a retry converges.
        if meeting.note_id is not None:
            await self._note_writer.delete_note(meeting.note_id)
            await self._notes_repository.soft_delete(meeting.note_id)

        # False means the row changed under us (re-summarizing, or a concurrent
        # delete won) — report it rather than claiming a delete that didn't happen.
        if not await self._meetings_repository.soft_delete(meeting.id):
            raise MeetingStillProcessingError(
                f"Meeting {meeting.id} changed state during delete; retry shortly."
            )
