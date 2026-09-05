"""GET /desktop/meetings/{meeting_id} — the desktop app's poll for a
finished summary. `MeetingNotFoundError` (404) is left to propagate to the
registered `AppError` exception handler.
"""

import uuid

from fastapi import APIRouter, BackgroundTasks, Depends

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import MeetingsServiceDep
from app.modules.meetings.api.schemas import DesktopMeetingStatusResponse, to_status_response

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.get("/meetings/{meeting_id}")
async def get_meeting_status(
    meeting_id: uuid.UUID,
    background_tasks: BackgroundTasks,
    service: MeetingsServiceDep,
) -> DesktopMeetingStatusResponse:
    meeting, needs_resummarization = await service.get_status(meeting_id)
    if needs_resummarization:
        background_tasks.add_task(service.summarize_and_publish, meeting_id)
    return to_status_response(meeting)
