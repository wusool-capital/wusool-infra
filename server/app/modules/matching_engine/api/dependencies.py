"""Composition roots for Slack handlers (§2, §36) — glue code: constructs
sessions/repositories/services and calls application-layer commands. No data
definitions here; those live in each concept's own `api/<concept>.py`.
"""

import logging
import uuid
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matching_engine.api.buyers import BuyerResolutionRead, BuyerSummary
from app.modules.matching_engine.api.matching import MatchAnalysis, MatchResultRead, MatchScoreRead
from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWorkFactory
from app.modules.matching_engine.application.service import MatchingEngineService
from app.modules.matching_engine.bootstrap import build_bedrock_client as _build_bedrock_client
from app.modules.matching_engine.bootstrap import (
    build_matching_engine_service,
    build_matching_unit_of_work_factory,
    build_slack_notifier,
)
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import MatchAnalysisData
from app.modules.matching_engine.domain.matching.scoring import needs_web_fallback
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.providers.bedrock.client import BedrockConverseClient
from app.modules.notifications import SlackWebClientNotifier

logger = logging.getLogger(__name__)


def _matching_unit_of_work_factory() -> MatchingUnitOfWorkFactory:
    return build_matching_unit_of_work_factory(
        get_sessionmaker(), meeting_notes_max_chars=get_settings().meeting_notes_max_chars
    )


@lru_cache
def _bedrock_client() -> BedrockConverseClient:
    return _build_bedrock_client()


def matching_engine_service(session: AsyncSession) -> MatchingEngineService:
    """`session` must stay open for as long as the returned service is in
    use — see `bootstrap.build_matching_engine_service`'s docstring."""
    return build_matching_engine_service(
        session,
        uow_factory=_matching_unit_of_work_factory(),
        sessionmaker=get_sessionmaker(),
        bedrock_client=_bedrock_client(),
    )


async def resolve_buyer(buyer_name: str) -> BuyerResolutionRead:
    async with get_sessionmaker()() as session:
        resolution = await matching_engine_service(session).resolve_buyer(buyer_name)
        candidates = (
            [BuyerSummary.from_candidate(c) for c in resolution.candidates]
            if resolution.candidates is not None
            else None
        )
        return BuyerResolutionRead(status=resolution.status, candidates=candidates)


async def resolve_buyer_by_id(buyer_role_id: str) -> BuyerContext | None:
    async with get_sessionmaker()() as session:
        return await matching_engine_service(session).resolve_buyer_by_id(buyer_role_id)


def to_match_analysis_schema(analysis: MatchAnalysisData) -> MatchAnalysis:
    """Domain -> Pydantic conversion at the api boundary — `application/`
    builds/returns `MatchAnalysisData` (domain), never this schema."""
    return MatchAnalysis(
        run=MatchResultRead.model_validate(analysis.run),
        candidates=[MatchResultRead.model_validate(c) for c in analysis.candidates],
        scores=[MatchScoreRead.model_validate(s) for s in analysis.scores],
    )


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
    # be circular.
    from app.modules.matching_engine.api.slack.views.match_result import build_match_result_blocks

    notifier = _build_slack_notifier()
    placeholder_ts: str | None = None
    discovery_run_id: uuid.UUID | None = None
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

        # The session backs buyer_repository/meeting_repository only —
        # run_match/search_web_leads never touch either (they use their own
        # short-lived uow_factory transactions), so it's closed right after
        # construction rather than held open for the full multi-second match
        # run. Both modules share one connection pool; holding it idle here
        # was starving concurrent runs and flapping /readiness.
        async with get_sessionmaker()() as session:
            service = matching_engine_service(session)

        result = await service.run_match(buyer, requested_by=requested_by)

        blocks = build_match_result_blocks(result)
        scores = [c.match_score for c in result.results]
        should_trigger_discovery = result.status == "GENERATED" and needs_web_fallback(
            scores, get_settings().web_fallback_min_score
        )

        await notifier.update_message(
            channel=channel_id,
            ts=placeholder_ts,
            text=f"Match results for {result.buyer_org_name}",
            blocks=blocks,
        )

        if should_trigger_discovery:
            discovery_run_id = uuid.UUID(result.run_id)

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
        return

    if discovery_run_id is not None:
        # Deliberately outside the block above and in its own try: a
        # below-threshold match was already successfully posted, so a
        # failure here must never overwrite that message with a generic
        # "matching failed" notice — it only logs.
        try:
            await trigger_seller_discovery(discovery_run_id, channel_id=channel_id)
        except Exception:
            logger.exception(
                "seller_discovery_trigger_failed",
                extra={"run_id": str(discovery_run_id), "channel_id": channel_id},
            )


async def trigger_seller_discovery(run_id: uuid.UUID, *, channel_id: str) -> None:
    """Below-threshold match quality: hand the run's own (industry,
    geography) off to `discovery`'s search, as a second message rather than
    replacing the match-results one — `discovery.find_and_post_leads` posts
    and owns its own placeholder/update pair.
    """
    from app.modules.discovery import find_and_post_leads
    from app.modules.matching_engine.application.discovery_bridge import extract_query_terms

    async with get_sessionmaker()() as session:
        service = matching_engine_service(session)
        analysis = await service.get_match_analysis(run_id)

    if analysis is None or analysis.run.requirement_profile is None:
        return

    industry, geography = extract_query_terms(analysis.run.requirement_profile)
    if not industry and not geography:
        return

    await find_and_post_leads(industry=industry, geography=geography, channel_id=channel_id)
