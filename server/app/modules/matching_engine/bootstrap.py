"""Composition root for this module's own FastAPI app: health/readiness,
exception handling, logging, and the Slack ASGI mount (§29 — Slack is the
only product interface; no public REST endpoints for
matching/buyer/seller/approval data). Also holds the `build_*` factory
functions `api/dependencies.py` calls instead of constructing concrete
persistence/provider classes inline.

`create_app()` exists for running this module in isolation (its own test
suite, `uv run --package matching_engine ...`-style standalone use) — the
actually-deployed process is `server/main.py`, which merges both modules'
Slack handlers onto one `AsyncApp` instead of calling this.
"""

import logging
from functools import lru_cache

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.matching_engine.application.matching.reasoning_service import (
    MatchReasoningService,
)
from app.modules.matching_engine.application.ports.llm import InferenceConfig
from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.application.requirements import (
    BuyerRequirementExtractionService,
)
from app.modules.matching_engine.application.service import MatchingEngineService
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.matching.scoring import ScoringEngine
from app.modules.matching_engine.persistence.candidate_retriever import (
    StructuredCandidateRetriever,
)
from app.modules.matching_engine.persistence.database import (
    check_database_connectivity,
    import_all_models,
)
from app.modules.matching_engine.persistence.repositories.buyers_repository import (
    BuyerRepository,
)
from app.modules.matching_engine.persistence.repositories.meetings_repository import (
    MeetingRepository,
)
from app.modules.matching_engine.persistence.unit_of_work import SqlAlchemyMatchingUnitOfWork
from app.modules.matching_engine.providers.bedrock.client import BedrockConverseClient
from app.modules.matching_engine.providers.firecrawl.client import FirecrawlMapsClient
from app.modules.notifications import SlackWebClientNotifier, get_slack_client
from app.modules.utilities.api.handlers import register_exception_handlers
from app.modules.utilities.domain.logging import configure_logging

_logger = logging.getLogger("app.modules.matching_engine.bootstrap")


def build_buyer_repository(session: AsyncSession) -> BuyerRepository:
    return BuyerRepository(session)


def build_meeting_repository(session: AsyncSession, *, max_chars: int) -> MeetingRepository:
    return MeetingRepository(session, max_chars=max_chars)


def build_bedrock_client() -> BedrockConverseClient:
    return BedrockConverseClient()


def build_firecrawl_client(api_key: str) -> FirecrawlMapsClient:
    return FirecrawlMapsClient(api_key)


def build_slack_notifier() -> SlackWebClientNotifier:
    return SlackWebClientNotifier(get_slack_client(get_settings().slack_bot_token))


def build_matching_unit_of_work_factory(
    sessionmaker: async_sessionmaker[AsyncSession], *, meeting_notes_max_chars: int
) -> MatchingUnitOfWorkFactory:
    def _factory() -> SqlAlchemyMatchingUnitOfWork:
        return SqlAlchemyMatchingUnitOfWork(
            sessionmaker, meeting_notes_max_chars=meeting_notes_max_chars
        )

    return _factory


def build_matching_engine_service(
    session: AsyncSession,
    *,
    uow_factory: MatchingUnitOfWorkFactory,
    sessionmaker: async_sessionmaker[AsyncSession],
    bedrock_client: BedrockConverseClient,
    firecrawl_client: FirecrawlMapsClient | None,
) -> MatchingEngineService:
    """`session` backs `buyer_repository`/`meeting_repository` — every
    method call this service makes must happen before that session closes,
    even the ones (`approve_match`, `run_match`, ...) that never touch
    those two repositories (see `application/base.py`'s docstring for why
    one shared constructor means every caller pays for this).
    """
    settings = get_settings()
    inference_config = InferenceConfig(
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        top_p=settings.llm_top_p,
    )
    return MatchingEngineService(
        uow_factory,
        buyer_repository=build_buyer_repository(session),
        meeting_repository=build_meeting_repository(
            session, max_chars=settings.meeting_notes_max_chars
        ),
        extraction_service=BuyerRequirementExtractionService(
            bedrock_client,
            model_id=settings.aws_bedrock_model_id_extraction,
            inference_config=inference_config,
            meeting_notes_char_budget=settings.meeting_notes_max_total_chars,
        ),
        reasoning_service=MatchReasoningService(
            bedrock_client,
            model_id=settings.aws_bedrock_model_id_reasoning,
            inference_config=inference_config,
            meeting_notes_char_budget=settings.meeting_notes_max_total_chars,
        ),
        candidate_retriever=StructuredCandidateRetriever(sessionmaker),
        scoring_engine=ScoringEngine(
            {
                "llm_extracted": settings.confidence.llm_extracted,
                "llm_inferred": settings.confidence.llm_inferred,
            }
        ),
        top_n=settings.stage3_top_n,
        enable_seller_meeting_notes=settings.enable_seller_meeting_notes,
        firecrawl_client=firecrawl_client,
    )


def create_app() -> FastAPI:
    # Local import: `api.slack.bolt_app` -> `api.slack.handlers` ->
    # `api.dependencies`, which imports this module's `build_*` factories —
    # a module-level import here would cycle. Safe deferred to call time:
    # by the time `create_app()` actually runs, every module is already
    # fully loaded.
    from app.modules.matching_engine.api.slack.bolt_app import get_bolt_app

    settings = get_settings()
    configure_logging(settings.log_level)
    import_all_models()

    app = FastAPI(title="Buyer-Seller Matching & Intelligence Platform")
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
            _logger.error("Readiness check failed", exc_info=True)
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.get("/readiness")
    async def readiness() -> JSONResponse:
        return await _readiness()

    @app.get("/ready")
    async def ready() -> JSONResponse:
        """Alias for `/readiness` (§29's naming)."""
        return await _readiness()

    @lru_cache
    def _slack_request_handler() -> AsyncSlackRequestHandler:
        return AsyncSlackRequestHandler(get_bolt_app())

    @app.post("/slack/events")
    async def slack_events(req: Request) -> Response:
        """The Slack callback endpoint. Signature verification happens
        inside Bolt via `SLACK_SIGNING_SECRET` — never trust a payload
        without it.
        """
        return await _slack_request_handler().handle(req)

    return app
