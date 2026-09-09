"""Aggregates this module's routers.

No prefix: the endpoint paths are the ones the migration spec names
(`/enrich`, `/analyze`, `/compare`, `/readiness/score`, `/buyer/apply`) plus
`/benchmark`, which keeps the path the live benchmark page already posts to.
"""

from fastapi import APIRouter

from app.modules.lead_magnets.api.tools import router as tools_router

router = APIRouter()
router.include_router(tools_router)
