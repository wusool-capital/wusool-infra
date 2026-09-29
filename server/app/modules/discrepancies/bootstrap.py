"""Composition root: holds the `build_*` factory functions `api/dependencies.py`
calls instead of constructing concrete provider classes inline. Mirrors
`enrichment`/`matching_engine`'s own `bootstrap.py`.

`create_app()` exists for running this module in isolation (its own test
suite's Slack-dispatch tests) — the actually-deployed process is
`server/main.py`.
"""

from functools import lru_cache

from fastapi import FastAPI, Request, Response
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.modules.discrepancies.config import get_settings
from app.modules.discrepancies.providers.bedrock.client import BedrockConverseClient
from app.modules.notifications import SlackWebClientNotifier, build_bolt_app, get_slack_client
from app.modules.utilities.api.handlers import register_exception_handlers
from app.modules.utilities.domain.logging import configure_logging


def build_bedrock_phraser() -> BedrockConverseClient:
    return BedrockConverseClient()


def build_slack_notifier() -> SlackWebClientNotifier:
    return SlackWebClientNotifier(get_slack_client(get_settings().slack_bot_token))


def create_app() -> FastAPI:
    # Local import: `api.slack.handlers` imports `api.dependencies`, which
    # imports this module's `build_*` factories — a module-level import
    # here would cycle.
    from app.modules.discrepancies.api.slack.handlers import register_handlers

    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Discrepancies")
    register_exception_handlers(app)

    @lru_cache
    def _slack_request_handler() -> AsyncSlackRequestHandler:
        bolt_app = build_bolt_app(
            settings.slack_bot_token, settings.slack_signing_secret, register_handlers
        )
        return AsyncSlackRequestHandler(bolt_app)

    @app.post("/slack/events")
    async def slack_events(req: Request) -> Response:
        return await _slack_request_handler().handle(req)

    return app
