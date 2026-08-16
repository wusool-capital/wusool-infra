"""The one deployed entrypoint for this Slack bot — a single process serving
all 5 commands: `/find-match` (matching-engine) and `/edit-seller`,
`/remove-seller`, `/edit-buyer`, `/remove-buyer` (ddl-commands).

Neither package's own `app/main.py` / `ddl_commands/main.py` is used here —
each still exists (and still works standalone, e.g. for running one
package's tests in isolation), but this file is what actually gets deployed.
It builds **one** `AsyncApp` and registers both packages' handlers against
it, so Slack's one-interactivity-URL-per-app requirement is satisfied by
construction, not by convention.
"""

from functools import lru_cache

from app.config import get_settings
from app.modules.slack.handlers import register_handlers as register_matching_engine_handlers
from app.shared.database import check_database_connectivity
from app.shared.database import import_all_models as import_matching_engine_models
from app.shared.errors import register_exception_handlers
from app.shared.logging import configure_logging
from ddl_commands.modules.slack.handlers import (
    register_handlers as register_ddl_commands_handlers,
)
from ddl_commands.shared.database import import_all_models as import_ddl_commands_models
from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp

settings = get_settings()
configure_logging(settings.log_level)
import_matching_engine_models()
import_ddl_commands_models()

app = FastAPI(title="Wusool Toolkit Bot")
register_exception_handlers(app)


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


async def _readiness() -> JSONResponse:
    """Readiness check. Confirms database connectivity via `SELECT 1`.

    Both packages connect to the same `DATABASE_URL` with their own
    independent engine/session — checking one is sufficient to confirm the
    database itself is reachable from this process.
    """
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
def _bolt_app() -> AsyncApp:
    bolt_app = AsyncApp(
        token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret
    )
    register_matching_engine_handlers(bolt_app)
    register_ddl_commands_handlers(bolt_app)
    return bolt_app


@lru_cache
def _slack_request_handler() -> AsyncSlackRequestHandler:
    return AsyncSlackRequestHandler(_bolt_app())


@app.post("/slack/events")
async def slack_events(req: Request) -> Response:
    """The one Slack callback endpoint for all 5 commands. Signature
    verification happens inside Bolt via `SLACK_SIGNING_SECRET` — never
    trust a payload without it.
    """
    return await _slack_request_handler().handle(req)
