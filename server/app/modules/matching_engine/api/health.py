"""Liveness/readiness endpoints (§29) — a plain FastAPI concept router,
aggregated with any future one by `router.py`.
"""

import logging

from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.modules.matching_engine.persistence.database import check_database_connectivity

router = APIRouter()
_logger = logging.getLogger("app.modules.matching_engine.bootstrap")


async def _readiness() -> JSONResponse:
    """Readiness check. Confirms database connectivity via `SELECT 1`."""
    try:
        await check_database_connectivity()
    except Exception:
        _logger.error("Readiness check failed", exc_info=True)
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ready"})


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


@router.get("/readiness")
async def readiness() -> JSONResponse:
    return await _readiness()


@router.get("/ready")
async def ready() -> JSONResponse:
    """Alias for `/readiness` (§29's naming)."""
    return await _readiness()
