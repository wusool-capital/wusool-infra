"""Aggregates every plain REST concept router in this module. Slack's own
`/slack/events` mount stays in `bootstrap.py` — it goes through Bolt's
`AsyncSlackRequestHandler`, not a route function like the ones here.
"""

from fastapi import APIRouter

from app.modules.ddl_commands.api.attio_sync import router as attio_sync_router
from app.modules.ddl_commands.api.health import router as health_router

router = APIRouter()
router.include_router(health_router)
router.include_router(attio_sync_router)

__all__ = ["router"]
