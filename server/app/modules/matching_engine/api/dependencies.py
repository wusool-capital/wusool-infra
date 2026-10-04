"""Composition roots for Slack handlers (§2, §36) — glue code: constructs
sessions/repositories/services and calls application-layer commands. No data
definitions here; those live in each concept's own `api/<concept>.py`.
"""

import logging
import uuid
from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.discrepancies import DiscrepancyCheckResult
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
from app.modules.matching_engine.domain.matching.entities import (
    DiscoveredCandidate,
    MatchAnalysisData,
)
from app.modules.matching_engine.domain.matching.scoring import needs_web_fallback
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.providers.bedrock.client import BedrockConverseClient
from app.modules.notifications import SlackWebClientNotifier
from app.modules.utilities import get_shared_idempotency_store

logger = logging.getLogger(__name__)

# One discovery search per run, however it's triggered — the automatic
# below-threshold trigger in `run_match_and_post` and the manual "Find more
# sellers" button both call `trigger_seller_discovery` with the same
# `run_id`, and the button stays visible/clickable after the automatic
# trigger already fired, so without this an operator clicking it (or a
# retried Slack delivery of that click) re-runs the search and posts a
# second, duplicate "Found N potential sellers" message.
_discovery_idempotency_store = get_shared_idempotency_store()


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


async def find_buyer_discrepancies(
    buyer_role_id: str, advisor_context: str | None
) -> DiscrepancyCheckResult | None:
    """Checks the buyer's profile for missing details and for conflicts with
    the advisor's typed context. Returns None if the buyer no longer exists.

    Errors are left to propagate on purpose: the popup then says "couldn't
    check" instead of wrongly showing that nothing is missing.
    """
    from app.modules.discrepancies import check_buyer_discrepancies
    from app.modules.matching_engine.providers.discrepancies.criteria_reader_adapter import (
        to_buyer_criteria,
    )

    buyer = await resolve_buyer_by_id(buyer_role_id)
    if buyer is None:
        return None
    return await check_buyer_discrepancies(to_buyer_criteria(buyer), advisor_context)


async def run_match_and_post(
    buyer_role_id: str,
    requested_by: str,
    channel_id: str,
    *,
    advisor_context: str | None = None,
    placeholder_ts: str | None = None,
) -> None:
    """Shared background-task body for running the match pipeline and
    posting its result to Slack — used by the discrepancy popup's "Run
    anyway" submit and by "Run match anyway" buttons on in-channel gate
    messages posted before the popup existed. Discrepancies are checked by
    the popup beforehand, never here.

    `placeholder_ts` lets a legacy "Run match anyway" button reuse its
    discrepancy-report message as the placeholder instead of posting a
    second one.

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
    discovery_run_id: uuid.UUID | None = None
    try:
        if placeholder_ts is None:
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

        result = await service.run_match(
            buyer, requested_by=requested_by, advisor_context=advisor_context
        )

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
    geography) off to `discovery`, which pre-filters against the CRM and
    auto-creates the genuinely new sellers. Those are appended to this run
    as `PENDING_REVIEW` rows and posted as a second message with
    Approve/Reject; name-only look-alikes are posted separately with an
    "Add as seller" button, and leads whose website Diffbot/PDL didn't
    confirm get one "Review & Save" message each, so a human decides before
    anything is written.
    """
    idempotency_key = f"discovery:{run_id}"
    if _discovery_idempotency_store.seen(idempotency_key):
        logger.info("seller_discovery_duplicate_trigger_skipped run_id=%s", run_id)
        return
    _discovery_idempotency_store.mark(idempotency_key)

    from app.modules.discovery import (
        build_needs_review_blocks,
        build_possible_duplicate_blocks,
        discover_and_create_sellers,
    )
    from app.modules.matching_engine.api.slack.views.discovered_candidates import (
        build_discovered_candidates_blocks,
    )
    from app.modules.matching_engine.application.discovery_bridge import extract_query_terms

    async with get_sessionmaker()() as session:
        service = matching_engine_service(session)
        analysis = await service.get_match_analysis(run_id)

    if analysis is None or analysis.run.requirement_profile is None:
        return

    industry, geography, exclude_terms = extract_query_terms(analysis.run.requirement_profile)
    if not industry and not geography:
        return

    notifier = _build_slack_notifier()
    placeholder_ts = await notifier.post_message(
        channel=channel_id, text="🔎 *_Searching for potential sellers…_*"
    )
    try:
        outcome = await discover_and_create_sellers(
            industry=industry,
            geography=geography,
            quota_key=analysis.run.buyer_role_id,
            exclude_terms=exclude_terms,
        )
    except Exception:
        logger.exception("seller_discovery_failed", extra={"run_id": str(run_id)})
        await notifier.update_message(
            channel=channel_id, ts=placeholder_ts, text="Seller search failed unexpectedly."
        )
        return
    if outcome.status != "ok":
        await notifier.update_message(
            channel=channel_id, ts=placeholder_ts, text=_DISCOVERY_STATUS_TEXT[outcome.status]
        )
        return

    try:
        async with get_sessionmaker()() as session:
            service = matching_engine_service(session)
        await service.append_discovered_candidates(
            run_id,
            [
                DiscoveredCandidate(
                    seller_role_id=str(created.seller_role_id),
                    seller_attio_id=created.org_attio_id,
                    source_url=created.source_url,
                )
                for created in outcome.created
            ],
        )
        view = await service.get_match_run_view(run_id)
    except Exception:
        # The sellers already exist in the CRM at this point, so this must not
        # read like the search failed, and it can't be retried.
        logger.exception("discovered_candidates_review_setup_failed", extra={"run_id": str(run_id)})
        names = ", ".join(c.org_name for c in outcome.created)
        await notifier.update_message(
            channel=channel_id,
            ts=placeholder_ts,
            text=(
                f"Created {len(outcome.created)} seller(s) in the CRM ({names}) but couldn't "
                "set them up for review. Find them in the CRM."
            ),
        )
        return

    notes = [f"{outcome.already_in_crm} more already in the CRM."] if outcome.already_in_crm else []
    if outcome.needs_review:
        count = len(outcome.needs_review)
        verb = "needs" if count == 1 else "need"
        notes.append(f"{count} {verb} a website review before saving (below).")
    if outcome.failed:
        notes.append(
            "Couldn't save: "
            + ", ".join(
                f"{f.lead.name} (partly saved: {'; '.join(f.landed)})" if f.landed else f.lead.name
                for f in outcome.failed
            )
            + "."
        )
    created_ids = {str(c.seller_role_id) for c in outcome.created}
    discovered = (
        [r for r in view.results if r.origin == "discovery" and r.seller_role_id in created_ids]
        if view is not None
        else []
    )
    if discovered:
        await notifier.update_message(
            channel=channel_id,
            ts=placeholder_ts,
            text=f"Found {len(discovered)} new seller(s)",
            blocks=build_discovered_candidates_blocks(discovered, notes=notes),
        )
    else:
        detail = " ".join(notes) or "No new potential sellers found."
        await notifier.update_message(
            channel=channel_id, ts=placeholder_ts, text=f"No new sellers created. {detail}"
        )

    # One message per lead: each can carry a dozen field sections, and
    # Slack caps a message at 50 blocks.
    for unverified in outcome.needs_review:
        await notifier.post_message(
            channel=channel_id,
            text=f"Website check for {unverified.draft.org_name}",
            blocks=build_needs_review_blocks(unverified),
        )

    if outcome.possible_duplicates:
        await notifier.post_message(
            channel=channel_id,
            text=f"{len(outcome.possible_duplicates)} possible duplicate(s) found",
            blocks=build_possible_duplicate_blocks(outcome.possible_duplicates),
        )


_DISCOVERY_STATUS_TEXT = {
    "disabled": "Seller discovery isn't configured.",
    "daily_cap_reached": "Daily discovery limit reached for this buyer. Try again tomorrow.",
}
