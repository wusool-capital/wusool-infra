"""Composition roots for Slack handlers (§2, §36) — glue code: constructs
sessions/repositories/services and calls application-layer commands. No data
definitions here; those live in each concept's own `api/<concept>.py`.
"""

import logging
import uuid
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import timedelta
from functools import lru_cache
from typing import Literal

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.discovery import DiscoveryOutcome
from app.modules.discrepancies import DiscrepancyCheckResult
from app.modules.matching_engine.api.buyers import BuyerResolutionRead, BuyerSummary
from app.modules.matching_engine.api.matching import MatchAnalysis, MatchResultRead, MatchScoreRead
from app.modules.matching_engine.application.matching.use_cases import (
    MatchResultView,
    MatchRunResult,
)
from app.modules.matching_engine.application.ports.seller_edits import SellerEditPort
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

logger = logging.getLogger(__name__)

_seller_edit_port_holder: SellerEditPort | None = None


def configure_seller_edit_port(port: SellerEditPort) -> None:
    global _seller_edit_port_holder
    _seller_edit_port_holder = port


def seller_edit_port() -> SellerEditPort:
    if _seller_edit_port_holder is None:
        raise RuntimeError(
            "matching_engine seller-edit port not configured — call "
            "configure_seller_edit_port() at startup"
        )
    return _seller_edit_port_holder


def _matching_unit_of_work_factory() -> MatchingUnitOfWorkFactory:
    return build_matching_unit_of_work_factory(get_sessionmaker())


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


@asynccontextmanager
async def open_matching_engine_service() -> AsyncIterator[MatchingEngineService]:
    """The service with its session open for as long as the caller uses it, as
    `build_matching_engine_service` requires. An idle session holds no connection."""
    async with get_sessionmaker()() as session:
        yield matching_engine_service(session)


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
        should_trigger_discovery = discovery_follows_match(result)

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


def discovery_follows_match(result: MatchRunResult) -> bool:
    """A successful run whose every score is below `WEB_FALLBACK_MIN_SCORE`
    searches outside the CRM on its own, from Slack or the web."""
    scores = [c.match_score for c in result.results]
    return result.status == "GENERATED" and needs_web_fallback(
        scores, get_settings().web_fallback_min_score
    )


DiscoveryRunKind = Literal[
    "duplicate", "no_profile", "no_terms", "search_failed", "unavailable", "setup_failed", "done"
]


@dataclass(frozen=True)
class RunDiscovery:
    """What one run's search outside the CRM did. Slack and the web report it
    in their own way; the search itself is this one function for both."""

    kind: DiscoveryRunKind
    outcome: DiscoveryOutcome | None = None
    discovered: tuple[MatchResultView, ...] = ()
    notes: tuple[str, ...] = ()

    def summary(self) -> str:
        created = self.outcome.created if self.outcome else ()
        match self.kind:
            case "duplicate":
                return "This run has already searched outside the CRM."
            case "no_profile":
                return "This run has no requirement profile."
            case "no_terms":
                return "The buyer's profile has no sector or geography to search on."
            case "search_failed":
                return "Seller search failed unexpectedly."
            case "unavailable":
                return DISCOVERY_STATUS_TEXT[self.outcome.status] if self.outcome else ""
            case "setup_failed":
                names = ", ".join(c.org_name for c in created)
                return (
                    f"Created {len(created)} seller(s) in the CRM ({names}) but couldn't "
                    "set them up for review. Find them in the CRM."
                )
            case "done":
                if self.discovered:
                    return f"Found {len(self.discovered)} new seller(s)"
                if created:
                    # Written to the CRM but not attached here; "none created" would mislead.
                    return (
                        f"Created {len(created)} seller(s) in the CRM but couldn't add them "
                        "to this run. Find them in the CRM."
                    )
                return "No new sellers created."


async def discover_sellers_for_run(
    run_id: uuid.UUID, *, on_search_start: Callable[[], Awaitable[None]] | None = None
) -> RunDiscovery:
    """Below-threshold match quality, or "Find more sellers": hand the run's own
    (industry, geography) to `discovery`, which pre-filters against the CRM and
    auto-creates the genuinely new sellers, then append them to this run as
    `PENDING_REVIEW` rows. One search per run, whichever path asks first,
    claimed on the run row so it holds across restarts.
    `on_search_start` runs once a search is certain, before it starts."""
    async with open_matching_engine_service() as service:
        stale_after = timedelta(minutes=get_settings().match_run_stale_after_minutes)
        if not await service.claim_discovery(run_id, stale_after=stale_after):
            logger.info("seller_discovery_duplicate_trigger_skipped run_id=%s", run_id)
            return RunDiscovery(kind="duplicate")

        result = await _search_claimed(service, run_id, on_search_start)
        # Only a search that created sellers holds its claim; anything else may be retried.
        kept = result.kind in ("done", "setup_failed")
        try:
            await service.finish_discovery(
                run_id,
                outcome=("done" if result.kind == "done" else "failed") if kept else None,
                message=result.summary() if kept else None,
                notes=result.notes,
            )
        except Exception:
            logger.exception("seller_discovery_record_failed", extra={"run_id": str(run_id)})
        return result


async def _search_claimed(
    service: MatchingEngineService,
    run_id: uuid.UUID,
    on_search_start: Callable[[], Awaitable[None]] | None,
) -> RunDiscovery:
    from app.modules.discovery import discover_and_create_sellers
    from app.modules.matching_engine.application.discovery_bridge import extract_query_terms

    analysis = await service.get_match_analysis(run_id)
    if analysis is None or analysis.run.requirement_profile is None:
        return RunDiscovery(kind="no_profile")

    industry, geography, exclude_terms = extract_query_terms(analysis.run.requirement_profile)
    if not industry and not geography:
        return RunDiscovery(kind="no_terms")

    if on_search_start is not None:
        await on_search_start()
    try:
        outcome = await discover_and_create_sellers(
            industry=industry,
            geography=geography,
            quota_key=analysis.run.buyer_role_id,
            exclude_terms=exclude_terms,
        )
    except Exception:
        logger.exception("seller_discovery_failed", extra={"run_id": str(run_id)})
        return RunDiscovery(kind="search_failed")
    if outcome.status != "ok":
        return RunDiscovery(kind="unavailable", outcome=outcome)

    notes = tuple(discovery_outcome_notes(outcome))
    try:
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
        return RunDiscovery(kind="setup_failed", outcome=outcome, notes=notes)

    created_ids = {str(c.seller_role_id) for c in outcome.created}
    discovered = (
        tuple(
            r for r in view.results if r.origin == "discovery" and r.seller_role_id in created_ids
        )
        if view is not None
        else ()
    )
    return RunDiscovery(kind="done", outcome=outcome, discovered=discovered, notes=notes)


async def trigger_seller_discovery(run_id: uuid.UUID, *, channel_id: str) -> None:
    """Slack's report of `discover_sellers_for_run`: a placeholder while it
    searches, then the new sellers with Approve/Reject, or why there are none."""
    from app.modules.matching_engine.api.slack.views.discovered_candidates import (
        build_discovered_candidates_blocks,
    )

    notifier = _build_slack_notifier()
    placeholder_ts: str | None = None

    async def _post_placeholder() -> None:
        nonlocal placeholder_ts
        placeholder_ts = await notifier.post_message(
            channel=channel_id, text="🔎 *_Searching for potential sellers…_*"
        )

    result = await discover_sellers_for_run(run_id, on_search_start=_post_placeholder)
    if placeholder_ts is None:
        return

    text = result.summary()
    if result.kind == "done" and result.discovered:
        await notifier.update_message(
            channel=channel_id,
            ts=placeholder_ts,
            text=text,
            blocks=build_discovered_candidates_blocks(list(result.discovered), notes=result.notes),
        )
        return
    if result.kind == "done" and result.outcome and result.outcome.created:
        text = f"{text} {' '.join(result.notes)}".strip()
    elif result.kind == "done":
        text = f"{text} {' '.join(result.notes) or 'No new potential sellers found.'}"
    await notifier.update_message(channel=channel_id, ts=placeholder_ts, text=text)


DISCOVERY_STATUS_TEXT = {
    "disabled": "Seller discovery isn't configured.",
    "daily_cap_reached": "Daily discovery limit reached for this buyer. Try again tomorrow.",
}


def discovery_outcome_notes(outcome: DiscoveryOutcome) -> list[str]:
    """Advisor-facing counts of the leads discovery skipped or couldn't save."""
    notes = [f"{outcome.already_in_crm} more already in the CRM."] if outcome.already_in_crm else []
    if outcome.awaiting_review:
        notes.append(f"{outcome.awaiting_review} still awaiting an earlier website review.")
    if outcome.unverified_skipped:
        notes.append(
            f"{outcome.unverified_skipped} skipped because their website didn't match Google Maps."
        )
    if outcome.possible_duplicates:
        notes.append(
            f"{outcome.possible_duplicates} skipped as possible duplicates "
            "(a similar name is already in the CRM)."
        )
    if outcome.failed:
        notes.append(
            "Couldn't save: "
            + ", ".join(
                f"{f.lead.name} (partly saved: {'; '.join(f.landed)})" if f.landed else f.lead.name
                for f in outcome.failed
            )
            + "."
        )
    return notes
