"""Composition roots for Slack handlers (§2, §36) — glue code: constructs
sessions/repositories/services and calls application-layer commands. No data
definitions here; those live in each concept's own `api/<concept>.py`.
"""

import logging
import uuid
from functools import lru_cache

from app.modules.matching_engine.api.buyers import BuyerResolutionRead, BuyerSummary
from app.modules.matching_engine.api.matching import MatchAnalysis, MatchResultRead, MatchScoreRead
from app.modules.matching_engine.application.approvals import (
    ApproveMatchUseCase,
    RejectMatchUseCase,
)
from app.modules.matching_engine.application.buyers import BuyerResolutionService
from app.modules.matching_engine.application.matching.reasoning_service import (
    MatchReasoningService,
)
from app.modules.matching_engine.application.matching.use_cases import (
    GetMatchAnalysisUseCase,
    GetMatchRunViewUseCase,
    RunBuyerSellerMatchUseCase,
)
from app.modules.matching_engine.application.ports.llm import InferenceConfig
from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.application.requirements import (
    BuyerRequirementExtractionService,
)
from app.modules.matching_engine.application.web_search import WebLeadSearchService
from app.modules.matching_engine.bootstrap import (
    build_bedrock_client,
    build_buyer_repository,
    build_firecrawl_client,
    build_matching_unit_of_work_factory,
    build_meeting_repository,
    build_slack_notifier,
)
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import MatchAnalysisData
from app.modules.matching_engine.domain.matching.scoring import ScoringEngine, needs_web_fallback
from app.modules.matching_engine.persistence.candidate_retriever import (
    StructuredCandidateRetriever,
)
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.providers.bedrock.client import BedrockConverseClient
from app.modules.matching_engine.providers.firecrawl.client import FirecrawlMapsClient
from app.modules.notifications import SlackWebClientNotifier

logger = logging.getLogger(__name__)


async def resolve_buyer(buyer_name: str) -> BuyerResolutionRead:
    async with get_sessionmaker()() as session:
        resolution = await BuyerResolutionService(build_buyer_repository(session)).resolve(
            buyer_name
        )
        candidates = (
            [BuyerSummary.from_candidate(c) for c in resolution.candidates]
            if resolution.candidates is not None
            else None
        )
        return BuyerResolutionRead(status=resolution.status, candidates=candidates)


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerContext | None:
    async with get_sessionmaker()() as session:
        meetings = build_meeting_repository(
            session, max_chars=get_settings().meeting_notes_max_chars
        )
        service = BuyerResolutionService(build_buyer_repository(session), meetings)
        return await service.resolve_by_id(buyer_role_id)


def build_approve_match_use_case() -> ApproveMatchUseCase:
    return ApproveMatchUseCase(_matching_unit_of_work_factory())


def build_reject_match_use_case() -> RejectMatchUseCase:
    return RejectMatchUseCase(_matching_unit_of_work_factory())


def _inference_config() -> InferenceConfig:
    settings = get_settings()
    return InferenceConfig(
        temperature=settings.llm_temperature,
        max_tokens=settings.llm_max_tokens,
        top_p=settings.llm_top_p,
    )


@lru_cache
def _bedrock_client() -> BedrockConverseClient:
    return build_bedrock_client()


def _matching_unit_of_work_factory() -> MatchingUnitOfWorkFactory:
    return build_matching_unit_of_work_factory(
        get_sessionmaker(), meeting_notes_max_chars=get_settings().meeting_notes_max_chars
    )


def build_run_match_use_case() -> RunBuyerSellerMatchUseCase:
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    bedrock = _bedrock_client()
    inference_config = _inference_config()

    return RunBuyerSellerMatchUseCase(
        _matching_unit_of_work_factory(),
        extraction_service=BuyerRequirementExtractionService(
            bedrock,
            model_id=settings.aws_bedrock_model_id_extraction,
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
        reasoning_service=MatchReasoningService(
            bedrock,
            model_id=settings.aws_bedrock_model_id_reasoning,
            inference_config=inference_config,
            meeting_notes_char_budget=settings.meeting_notes_max_total_chars,
        ),
        top_n=settings.stage3_top_n,
        enable_seller_meeting_notes=settings.enable_seller_meeting_notes,
    )


def build_match_analysis_use_case() -> GetMatchAnalysisUseCase:
    return GetMatchAnalysisUseCase(_matching_unit_of_work_factory())


def to_match_analysis_schema(analysis: MatchAnalysisData) -> MatchAnalysis:
    """Domain -> Pydantic conversion at the api boundary — `application/`
    builds/returns `MatchAnalysisData` (domain), never this schema."""
    return MatchAnalysis(
        run=MatchResultRead.model_validate(analysis.run),
        candidates=[MatchResultRead.model_validate(c) for c in analysis.candidates],
        scores=[MatchScoreRead.model_validate(s) for s in analysis.scores],
    )


def build_match_run_view_use_case() -> GetMatchRunViewUseCase:
    return GetMatchRunViewUseCase(_matching_unit_of_work_factory())


@lru_cache
def _firecrawl_client() -> FirecrawlMapsClient | None:
    api_key = get_settings().firecrawl_api_key
    if not api_key:
        # `@lru_cache` means this fires once, not per-run — loud enough to
        # show up in CloudWatch without spamming every no-match request.
        logger.warning(
            "firecrawl_api_key_unset — Google-Maps web-fallback is disabled; "
            "set FIRECRAWL_API_KEY to enable it"
        )
        return None
    return build_firecrawl_client(api_key)


def build_web_lead_search_service() -> WebLeadSearchService | None:
    """Returns `None` when no `FIRECRAWL_API_KEY` is configured — the caller
    must treat that the same as "no leads found" and fall back to the plain
    no-candidates message, not crash."""
    client = _firecrawl_client()
    return WebLeadSearchService(_matching_unit_of_work_factory(), client) if client else None


def _build_slack_notifier() -> SlackWebClientNotifier:
    return build_slack_notifier()


async def run_match_and_post(buyer_role_id: str, requested_by: str, channel_id: str) -> None:
    """Shared background-task body for running the match pipeline and
    posting its result to Slack — used by both the `/find-match` command
    handler and the buyer-selection modal submission handler.

    Uses the shared out-of-band Slack notifier (no live Slack request in
    flight by the time this runs), not `get_bolt_app().client` — that used
    to build a second, throwaway `AsyncApp`, re-registering every Slack
    handler a second time, just to reach `.client`.
    """
    # Local imports: these live under api/slack/, which imports this
    # module's caller (handlers/actions.py) — a top-level import here would
    # be circular. `build_run_match_use_case`/`build_web_lead_search_service`
    # are defined above in this same file, no import needed for those.
    from app.modules.matching_engine.api.slack.views.match_result import build_match_result_blocks
    from app.modules.matching_engine.api.slack.views.web_fallback import build_web_fallback_blocks

    notifier = _build_slack_notifier()
    placeholder_ts: str | None = None
    try:
        placeholder_ts = await notifier.post_message(
            channel=channel_id, text="✨ *_Finding matches, please wait…_*"
        )

        buyer = await resolve_buyer_by_id(buyer_role_id)
        if buyer is None:
            await notifier.update_message(
                channel=channel_id,
                ts=placeholder_ts,
                text="Buyer not found.",
            )
            return

        result = await build_run_match_use_case().execute(buyer, requested_by=requested_by)

        blocks = build_match_result_blocks(result)
        scores = [c.match_score for c in result.results]
        if result.status == "GENERATED" and needs_web_fallback(
            scores, get_settings().web_fallback_min_score
        ):
            await notifier.update_message(
                channel=channel_id,
                ts=placeholder_ts,
                text="✨ *_No match found, searching Google Maps for potential sellers…_*",
            )

            lead_search = build_web_lead_search_service()
            leads = await lead_search.search(uuid.UUID(result.run_id)) if lead_search else []
            logger.info(
                "web_fallback_triggered run_id=%s leads_found=%d",
                result.run_id,
                len(leads),
                extra={"run_id": result.run_id, "leads_found": len(leads)},
            )
            if leads:
                blocks = build_web_fallback_blocks(result.buyer_org_name, leads)

        await notifier.update_message(
            channel=channel_id,
            ts=placeholder_ts,
            text=f"Match results for {result.buyer_org_name}",
            blocks=blocks,
        )
    except Exception:
        logger.exception(
            "match_dispatch_failed",
            extra={"buyer_role_id": buyer_role_id, "channel_id": channel_id},
        )
        if placeholder_ts is None:
            return
        try:
            await notifier.update_message(
                channel=channel_id,
                ts=placeholder_ts,
                text="Matching failed unexpectedly. Please try again.",
            )
        except Exception:
            logger.exception(
                "match_dispatch_failure_notification_failed",
                extra={"buyer_role_id": buyer_role_id, "channel_id": channel_id},
            )
