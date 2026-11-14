"""Post-push note edits from the desktop app (AZM-173). The summary is not
re-run: notes steer it only at first push, later edits are stored as-is.
"""

from __future__ import annotations

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.application.errors import MeetingNotFoundError


class UserNotesMixin(ServiceBase):
    async def update_user_notes(
        self, install_id: str, local_recording_id: str, user_notes: str | None
    ) -> None:
        meeting = await self._meetings_repository.get_by_install_and_recording(
            install_id, local_recording_id
        )
        # 404 for a soft-deleted meeting too, so the desktop stops retrying.
        if meeting is None or meeting.removed_at is not None:
            raise MeetingNotFoundError(
                f"Meeting for install {install_id} / recording {local_recording_id} not found"
            )
        cleaned = user_notes.strip() if user_notes else None
        if not await self._meetings_repository.update_user_notes(
            meeting.id, user_notes=cleaned or None
        ):
            raise MeetingNotFoundError(f"Meeting {meeting.id} not found")
