"""Aggregates every plain REST concept router in this module. Slack's own
`/slack/events` mount stays in `bootstrap.py` — it goes through Bolt's
`AsyncSlackRequestHandler`, not a route function like the ones here.
"""

from fastapi import APIRouter

from app.modules.matching_engine.api.health import router as health_router

router = APIRouter()
router.include_router(health_router)

__all__ = ["router"]
