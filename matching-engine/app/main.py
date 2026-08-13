"""Application entrypoint.

Matching, Slack workflow, and LLM business-logic endpoints are not
implemented in this phase — this wires the app skeleton: health/readiness,
exception handling, and logging.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.shared.database.engine import check_database_connectivity
from app.shared.errors import register_exception_handlers
from app.shared.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)

app = FastAPI(title="Buyer-Seller Matching & Intelligence Platform")
register_exception_handlers(app)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


@app.get("/readiness")
async def readiness() -> JSONResponse:
    """Readiness check. Confirms database connectivity via `SELECT 1`."""
    try:
        await check_database_connectivity()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ready"})
