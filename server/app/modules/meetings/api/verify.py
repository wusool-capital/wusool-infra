"""GET /desktop/verify — lets the desktop app's Push Destination settings
check a server URL + API key before saving them. All the work is done by
`require_desktop_api_key`: reaching the handler at all already proves the
Bearer token is correct, so the body just confirms that. Deliberately no
DB session — a config check shouldn't fail because Postgres is briefly
down; `/readiness` in main.py already covers that.
"""

from fastapi import APIRouter, Depends

from app.modules.meetings.api.auth import require_desktop_api_key
from app.modules.meetings.api.schemas import DesktopVerifyResponse

router = APIRouter(
    prefix="/desktop", tags=["desktop"], dependencies=[Depends(require_desktop_api_key)]
)


@router.get("/verify")
async def verify_desktop_config() -> DesktopVerifyResponse:
    return DesktopVerifyResponse()
