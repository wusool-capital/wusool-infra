"""Post-push note edits from the desktop app (AZM-173). The summary is not
re-run: notes steer it only at first push. Once the meeting's CRM note
exists, its "Advisor notes" section is rewritten too: Attio first, then
Postgres (see `ddl_commands/README.md`), so an Attio failure raises and
the desktop retries with nothing half-written.
"""

from __future__ import annotations

from app.modules.meetings.application.base import ServiceBase
from app.modules.meetings.application.errors import MeetingNotFoundError
from app.modules.meetings.domain.rendering import render_note_content


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
        # Still summarizing: the publish step reads the latest notes itself.
        if meeting.note_id is not None and meeting.summary is not None:
            content = render_note_content(meeting.summary, user_notes)
            if not meeting.skip_attio:
                await self._note_writer.update_note_content(meeting.note_id, content)
            await self._notes_repository.update_content(meeting.note_id, content)
        if not await self._meetings_repository.update_user_notes(meeting.id, user_notes=user_notes):
            raise MeetingNotFoundError(f"Meeting {meeting.id} not found")
