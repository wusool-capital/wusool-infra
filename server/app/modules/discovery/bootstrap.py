"""Composition root: holds the `build_*` factory functions `api/dependencies.py`
calls instead of constructing concrete persistence/provider classes inline.

`create_app()` exists for running this module in isolation (its own test
suite's Slack-dispatch tests, `uv run --package discovery ...`-style
standalone use) — the actually-deployed process is `server/main.py`.
"""

from functools import lru_cache

from fastapi import FastAPI, Request, Response
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler

from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.application.service import DiscoveryService
from app.modules.discovery.config import get_settings
from app.modules.discovery.providers.firecrawl.client import FirecrawlMapsClient
from app.modules.notifications import build_bolt_app
from app.modules.utilities.api.handlers import register_exception_handlers
from app.modules.utilities.domain.logging import configure_logging


def build_lead_search_client(api_key: str) -> FirecrawlMapsClient:
    return FirecrawlMapsClient(api_key)


def build_discovery_service(
    *,
    lead_search_client: FirecrawlMapsClient | None,
    seller_draft_port: SellerDraftPort,
) -> DiscoveryService:
    return DiscoveryService(
        lead_search_client=lead_search_client, seller_draft_port=seller_draft_port
    )


def create_app() -> FastAPI:
    # Local import: `api.slack.handlers` imports `api.dependencies`, which
    # imports this module's `build_*` factories — a module-level import
    # here would cycle.
    from app.modules.discovery.api.slack.handlers import register_handlers

    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Discovery")
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
