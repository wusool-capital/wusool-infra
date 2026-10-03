"""DELETE /desktop/meetings/{install_id}/{local_recording_id} — the desktop
app's "also delete from Wusool server & Attio" checkbox (AZM-126). Keyed by
the same pair `POST /desktop/meetings` dedupes on: the desktop app never
learns the server's own `meeting_id` (see `ingest.py`'s docstring), so this
is the only identifier it has to delete by.

Returns 204 for a meeting that never existed or was already removed
(`DeleteMixin.delete_meeting` is deliberately idempotent — see its
docstring) and lets `MeetingStillProcessingError` (409) propagate to the
registered `AppError` exception handler.
"""

from fastapi import APIRouter, Depends, Response, status

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.dependencies import MeetingsServiceDep

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.delete(
    "/meetings/{install_id}/{local_recording_id}", status_code=status.HTTP_204_NO_CONTENT
)
async def delete_meeting(
    install_id: str,
    local_recording_id: str,
    service: MeetingsServiceDep,
) -> Response:
    await service.delete_meeting(install_id, local_recording_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
