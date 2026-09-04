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
    build_firecrawl_client as _build_firecrawl_client,
)
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
from app.modules.matching_engine.providers.firecrawl.client import FirecrawlMapsClient
from app.modules.notifications import SlackWebClientNotifier

logger = logging.getLogger(__name__)


def _matching_unit_of_work_factory() -> MatchingUnitOfWorkFactory:
    return build_matching_unit_of_work_factory(
        get_sessionmaker(), meeting_notes_max_chars=get_settings().meeting_notes_max_chars
    )


@lru_cache
def _bedrock_client() -> BedrockConverseClient:
    return _build_bedrock_client()


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
    return _build_firecrawl_client(api_key)


def matching_engine_service(session: AsyncSession) -> MatchingEngineService:
    """`session` must stay open for as long as the returned service is in
    use — see `bootstrap.build_matching_engine_service`'s docstring."""
    return build_matching_engine_service(
        session,
        uow_factory=_matching_unit_of_work_factory(),
        sessionmaker=get_sessionmaker(),
        bedrock_client=_bedrock_client(),
        firecrawl_client=_firecrawl_client(),
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

        async with get_sessionmaker()() as session:
            service = matching_engine_service(session)
            result = await service.run_match(buyer, requested_by=requested_by)

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

                leads = await service.search_web_leads(uuid.UUID(result.run_id))
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
