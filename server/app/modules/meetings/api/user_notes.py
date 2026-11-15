"""PUT /desktop/meetings/{install_id}/{local_recording_id}/user-notes — syncs
notes the user edits after the first push (AZM-173). Keyed like `delete.py`
because the desktop never learns the server's `meeting_id`.

`MeetingNotFoundError` (404, also for a soft-deleted meeting) propagates to
the registered `AppError` handler.
"""

from fastapi import APIRouter, Depends, Response, status

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import MeetingsServiceDep
from app.modules.meetings.api.schemas import DesktopMeetingUserNotesRequest

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.put(
    "/meetings/{install_id}/{local_recording_id}/user-notes",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def update_user_notes(
    install_id: str,
    local_recording_id: str,
    request: DesktopMeetingUserNotesRequest,
    service: MeetingsServiceDep,
) -> Response:
    await service.update_user_notes(install_id, local_recording_id, request.user_notes)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
