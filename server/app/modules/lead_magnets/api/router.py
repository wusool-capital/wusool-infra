"""Aggregates this module's per-tool routers.

No prefix: the endpoint paths are the ones the migration spec names
(`/enrich`, `/analyze`, `/compare`, `/readiness/score`, `/buyer/apply`) plus
`/benchmark`, which keeps the path the live benchmark page already posts to.
"""

from fastapi import APIRouter

from app.modules.lead_magnets.api.benchmark.endpoints import router as benchmark_router
from app.modules.lead_magnets.api.readiness.endpoints import router as readiness_router
from app.modules.lead_magnets.api.valuation.endpoints import router as valuation_router

router = APIRouter()
router.include_router(benchmark_router)
router.include_router(readiness_router)
router.include_router(valuation_router)
