"""Application entrypoint: health/readiness, exception handling, logging,
and the Slack ASGI mount. Slack is the only product interface — no public
REST endpoints for buyer/seller data.
"""

from functools import lru_cache

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.config import get_settings
from app.modules.slack.bolt_app import get_bolt_app
from app.shared.database import check_database_connectivity, import_all_models
from app.shared.errors import register_exception_handlers
from app.shared.logging import configure_logging

settings = get_settings()
configure_logging(settings.log_level)
import_all_models()

app = FastAPI(title="DDL Commands — Buyer/Seller Profile Editor")
register_exception_handlers(app)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


async def _readiness() -> JSONResponse:
    """Readiness check. Confirms database connectivity via `SELECT 1`."""
    try:
        await check_database_connectivity()
    except Exception:
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/readiness")
async def readiness() -> JSONResponse:
    return await _readiness()


@app.get("/ready")
async def ready() -> JSONResponse:
    """Alias for `/readiness`."""
    return await _readiness()


@lru_cache
def _slack_request_handler() -> AsyncSlackRequestHandler:
    return AsyncSlackRequestHandler(get_bolt_app())


@app.post("/slack/events")
async def slack_events(req: Request) -> Response:
    """The Slack callback endpoint. Signature verification happens inside
    Bolt via `SLACK_SIGNING_SECRET` — never trust a payload without it.
    """
    return await _slack_request_handler().handle(req)
