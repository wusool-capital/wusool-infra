"""GET /desktop/meetings?install_id=&limit= — the desktop app's cheap
sync-on-launch/background reconcile listing (status only, no summary
body). `limit` bounds match Scribe's own `list_meetings_for_install`.
"""

from fastapi import APIRouter, Depends, Query

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import MeetingsServiceDep
from app.modules.meetings.api.schemas import DesktopMeetingSyncResponse, to_sync_item

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.get("/meetings")
async def list_meetings_for_install(
    service: MeetingsServiceDep,
    install_id: str = Query(..., min_length=1, max_length=64),
    limit: int = Query(default=200, ge=1, le=500),
) -> DesktopMeetingSyncResponse:
    statuses = await service.list_for_install(install_id, limit=limit)
    return DesktopMeetingSyncResponse(meetings=[to_sync_item(status) for status in statuses])
