"""The one deployed entrypoint for this Slack bot — a single process serving
all 5 commands: `/find-match` (matching_engine module) and `/edit-seller`,
`/edit-buyer`, `/add-seller`, `/add-buyer` (ddl_commands module).

Builds **one** `AsyncApp` and registers both modules' handlers against it, so
Slack's one-interactivity-URL-per-app requirement is satisfied by
construction, not by convention. Neither module's own `bootstrap.create_app()`
is used here — each exists for running that module standalone (its own test
suite) — this file is what actually gets deployed.
"""

import logging
import time
from collections.abc import Awaitable, Callable
from functools import lru_cache

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from slack_bolt.async_app import AsyncApp
from slack_bolt.response import BoltResponse

from app.modules.ddl_commands.api.attio_sync import router as attio_sync_router
from app.modules.ddl_commands.api.slack.handlers import (
    register_handlers as register_ddl_commands_handlers,
)
from app.modules.ddl_commands.persistence.database import (
    import_all_models as import_ddl_commands_models,
)
from app.modules.matching_engine.api.slack.handlers import (
    register_handlers as register_matching_engine_handlers,
)
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.persistence.database import check_database_connectivity
from app.modules.matching_engine.persistence.database import (
    import_all_models as import_matching_engine_models,
)
from app.modules.utilities.api.handlers import register_exception_handlers
from app.modules.utilities.domain.logging import configure_logging, log_context

settings = get_settings()
configure_logging(settings.log_level)
import_matching_engine_models()
import_ddl_commands_models()

# Which service owns each command/interaction trigger Slack can send. Bolt's
# own global error handler always logs a caught exception under its own
# `slack_bolt.AsyncApp` logger, with no indication of which command or
# action actually failed short of reading the full traceback — this map lets
# the handler below say so explicitly.
_SERVICE_BY_TRIGGER: dict[str, str] = {
    "/find-match": "matching-engine",
    "/edit-seller": "ddl-commands",
    "/edit-buyer": "ddl-commands",
    "/add-seller": "ddl-commands",
    "/add-buyer": "ddl-commands",
}
_UNKNOWN_TRIGGER = "unknown"
_slack_dispatch_logger = logging.getLogger("toolkit.slack_dispatch")

# Bolt's own `ack_timeout` is 3s; warn a little under it so a request that is
# merely close to the edge still shows up before it starts failing outright.
_ACK_BUDGET_MS = 2500

app = FastAPI(title="Wusool Toolkit Bot")
register_exception_handlers(app)
app.include_router(attio_sync_router)


@app.exception_handler(Exception)
async def _log_unhandled_exception(request: Request, exc: Exception) -> JSONResponse:
    """Catches anything that isn't an `AppError` — without this, a route
    exception escapes to Starlette's default handler and bypasses our
    formatter/logger entirely."""
    _slack_dispatch_logger.error(
        "Unhandled exception on %s %s", request.method, request.url.path, exc_info=exc
    )
    return JSONResponse(status_code=500, content={"detail": "internal server error"})


@app.get("/health")
async def health() -> dict[str, str]:
    """Liveness check. Does not touch the database."""
    return {"status": "ok"}


async def _readiness() -> JSONResponse:
    """Readiness check. Confirms database connectivity via `SELECT 1`.

    Both modules connect to the same `DATABASE_URL` with their own
    independent engine/session — checking one is sufficient to confirm the
    database itself is reachable from this process.
    """
    try:
        await check_database_connectivity()
    except Exception:
        _slack_dispatch_logger.error("Readiness check failed", exc_info=True)
        return JSONResponse(status_code=503, content={"status": "unavailable"})
    return JSONResponse(status_code=200, content={"status": "ready"})


@app.get("/readiness")
async def readiness() -> JSONResponse:
    return await _readiness()


@app.get("/ready")
async def ready() -> JSONResponse:
    """Alias for `/readiness`."""
    return await _readiness()


def _extract_trigger(body: dict) -> str:
    """Best-effort: which slash command, block action, or view submission
    this payload came from. Slack's payload shape differs by interaction
    type, so check each in turn rather than assuming one key exists.
    """
    if command := body.get("command"):
        return command
    if actions := body.get("actions"):
        if action_id := actions[0].get("action_id"):
            return action_id
    if callback_id := body.get("view", {}).get("callback_id"):
        return callback_id
    return _UNKNOWN_TRIGGER


@lru_cache
def _bolt_app() -> AsyncApp:
    bolt_app = AsyncApp(
        token=settings.slack_bot_token, signing_secret=settings.slack_signing_secret
    )
    register_matching_engine_handlers(bolt_app)
    register_ddl_commands_handlers(bolt_app)

    @bolt_app.middleware
    async def _set_log_context(
        body: dict, next: Callable[[], Awaitable[BoltResponse]]
    ) -> None:
        """Tags every log line emitted while handling this request with
        which command/action triggered it and who sent it — set once here
        rather than threading it through every handler."""
        trigger = _extract_trigger(body)
        token = log_context.set(
            {
                "trigger": trigger,
                "slack_service": _SERVICE_BY_TRIGGER.get(trigger, _UNKNOWN_TRIGGER),
                "user_id": body.get("user_id") or (body.get("user") or {}).get("id"),
                "channel_id": body.get("channel_id") or (body.get("channel") or {}).get("id"),
            }
        )
        started = time.monotonic()
        try:
            await next()
        finally:
            # `next()` returns when the listener calls `ack()`, not when it
            # finishes — so this measures ack latency specifically. That's the
            # number Slack budgets 3s for. Overrun it on a view submission and
            # Bolt's runner stops waiting, logs only at WARNING under its own
            # logger, and returns an empty 200: no exception, so the
            # `@bolt_app.error` handler below never fires and the operator just
            # sees Slack's "We had some trouble connecting". Log it here or it
            # is invisible.
            elapsed_ms = (time.monotonic() - started) * 1000
            if elapsed_ms > _ACK_BUDGET_MS:
                _slack_dispatch_logger.warning(
                    "Slow ack for %s: %.0fms (Slack abandons the request at 3000ms)",
                    trigger,
                    elapsed_ms,
                )
            log_context.reset(token)

    @bolt_app.error
    async def _log_uncaught_listener_error(error: Exception, body: dict) -> None:
        trigger = _extract_trigger(body)
        service = _SERVICE_BY_TRIGGER.get(trigger, _UNKNOWN_TRIGGER)
        _slack_dispatch_logger.error(
            "[%s] Slack listener failed for %s", service, trigger, exc_info=error
        )

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
