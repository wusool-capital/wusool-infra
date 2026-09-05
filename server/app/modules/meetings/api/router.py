"""Aggregates every desktop endpoint router in this module — the module's
only HTTP surface. Each endpoint file's own router carries its own
`prefix="/desktop"`, matching how matching_engine's `health_router` carries
its own prefix.
"""

from fastapi import APIRouter

from app.modules.meetings.api.companies import router as companies_router
from app.modules.meetings.api.ingest import router as ingest_router
from app.modules.meetings.api.status import router as status_router
from app.modules.meetings.api.sync import router as sync_router

router = APIRouter()
router.include_router(ingest_router)
router.include_router(status_router)
router.include_router(sync_router)
router.include_router(companies_router)

__all__ = ["router"]
