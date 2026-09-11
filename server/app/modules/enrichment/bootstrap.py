"""Composition root: holds the `build_*` factory functions `api/dependencies.py`
calls instead of constructing concrete persistence/provider classes inline.
Mirrors `matching_engine`/`ddl_commands`'s own `bootstrap.py`.

`create_app()` exists for running this module in isolation (its own test
suite's Slack-dispatch tests, `uv run --package enrichment ...`-style
standalone use) — the actually-deployed process is `server/main.py`.
"""

from functools import lru_cache

from fastapi import FastAPI, Request, Response
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.enrichment.application.ports.company_data import CompanyDataClient
from app.modules.enrichment.application.ports.review import EnrichmentReviewPort
from app.modules.enrichment.application.service import EnrichmentService
from app.modules.enrichment.config import get_settings
from app.modules.enrichment.persistence.role_lookup import SqlAlchemyRoleReader
from app.modules.enrichment.providers.bedrock.client import BedrockConverseClient
from app.modules.enrichment.providers.diffbot.client import DiffbotCompanyDataClient
from app.modules.enrichment.providers.firecrawl.client import FirecrawlResearchClient
from app.modules.enrichment.providers.people_data_labs.client import (
    PeopleDataLabsCompanyDataClient,
)
from app.modules.notifications import SlackWebClientNotifier, build_bolt_app, get_slack_client
from app.modules.utilities.api.handlers import register_exception_handlers
from app.modules.utilities.domain.logging import configure_logging


def build_bedrock_client() -> BedrockConverseClient:
    return BedrockConverseClient()


def build_research_client(api_key: str) -> FirecrawlResearchClient:
    return FirecrawlResearchClient(api_key)


def build_diffbot_client(api_key: str) -> DiffbotCompanyDataClient:
    return DiffbotCompanyDataClient(api_key)


def build_people_data_labs_client(api_key: str) -> PeopleDataLabsCompanyDataClient:
    return PeopleDataLabsCompanyDataClient(api_key)


def build_role_reader(sessionmaker: async_sessionmaker[AsyncSession]) -> SqlAlchemyRoleReader:
    return SqlAlchemyRoleReader(sessionmaker)


def build_slack_notifier() -> SlackWebClientNotifier:
    return SlackWebClientNotifier(get_slack_client(get_settings().slack_bot_token))


def build_enrichment_service(
    *,
    sessionmaker: async_sessionmaker[AsyncSession],
    bedrock_client: BedrockConverseClient,
    research_client: FirecrawlResearchClient | None,
    review_port: EnrichmentReviewPort,
    company_data_clients: tuple[CompanyDataClient, ...] = (),
) -> EnrichmentService:
    settings = get_settings()
    return EnrichmentService(
        research_client=research_client,
        extraction_client=bedrock_client,
        role_reader=build_role_reader(sessionmaker),
        review_port=review_port,
        model_id=settings.aws_bedrock_model_id_extraction,
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        min_confidence=settings.enrichment_min_confidence,
        company_data_clients=company_data_clients,
    )


def create_app() -> FastAPI:
    # Local import: `api.slack.handlers` imports `api.dependencies`, which
    # imports this module's `build_*` factories — a module-level import
    # here would cycle.
    from app.modules.enrichment.api.slack.handlers import register_handlers

    settings = get_settings()
    configure_logging(settings.log_level)

    app = FastAPI(title="Enrichment")
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
