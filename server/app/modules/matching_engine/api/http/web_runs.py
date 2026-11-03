"""Background body of a web find-match run: the match itself, then — when every
score is below `WEB_FALLBACK_MIN_SCORE` — discovery, the same follow-up Slack
runs get. Progress lands in `run_tracker` and the persisted rows; nothing is
posted to Slack.
"""

import logging
import uuid

from app.modules.matching_engine.api.dependencies import (
    DISCOVERY_STATUS_TEXT,
    detached_matching_engine_service,
    discovery_outcome_notes,
)
from app.modules.matching_engine.api.http.run_tracker import TrackedDiscovery, run_tracker
from app.modules.matching_engine.application.matching.use_cases import StartedRun
from app.modules.matching_engine.config import get_settings
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import DiscoveredCandidate
from app.modules.matching_engine.domain.matching.scoring import needs_web_fallback
from app.modules.utilities import get_shared_idempotency_store

logger = logging.getLogger(__name__)

# Same store and key as the Slack trigger, so one run never searches twice.
_discovery_idempotency_store = get_shared_idempotency_store()


async def execute_web_run(
    started: StartedRun, buyer: BuyerContext, *, advisor_context: str | None
) -> None:
    service = await detached_matching_engine_service()
    # `execute_run` records its own failures on the run row.
    result = await service.execute_run(started, buyer, None, advisor_context=advisor_context)
    run_tracker.set_notes(started.run_id, result.notes)

    scores = [c.match_score for c in result.results]
    if result.status != "GENERATED" or not needs_web_fallback(
        scores, get_settings().web_fallback_min_score
    ):
        run_tracker.set_discovery(started.run_id, TrackedDiscovery(status="not_needed"))
        return
    await discover_for_web_run(started.run_id)


async def discover_for_web_run(run_id: uuid.UUID) -> None:
    key = f"discovery:{run_id}"
    if _discovery_idempotency_store.seen(key):
        return
    _discovery_idempotency_store.mark(key)
    run_tracker.set_discovery(run_id, TrackedDiscovery(status="running"))
    try:
        run_tracker.set_discovery(run_id, await _discover(run_id))
    except Exception:
        logger.exception("web_seller_discovery_failed", extra={"run_id": str(run_id)})
        run_tracker.set_discovery(
            run_id,
            TrackedDiscovery(status="failed", message="Seller search failed unexpectedly."),
        )


async def _discover(run_id: uuid.UUID) -> TrackedDiscovery:
    from app.modules.discovery import discover_and_create_sellers
    from app.modules.matching_engine.application.discovery_bridge import extract_query_terms

    service = await detached_matching_engine_service()
    analysis = await service.get_match_analysis(run_id)
    if analysis is None or analysis.run.requirement_profile is None:
        return TrackedDiscovery(status="skipped", message="This run has no requirement profile.")

    industry, geography, exclude_terms = extract_query_terms(analysis.run.requirement_profile)
    if not industry and not geography:
        return TrackedDiscovery(
            status="skipped",
            message="The buyer's profile has no sector or geography to search on.",
        )

    outcome = await discover_and_create_sellers(
        industry=industry,
        geography=geography,
        quota_key=analysis.run.buyer_role_id,
        exclude_terms=exclude_terms,
    )
    if outcome.status != "ok":
        return TrackedDiscovery(status="unavailable", message=DISCOVERY_STATUS_TEXT[outcome.status])

    notes = discovery_outcome_notes(outcome)
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
    except Exception:
        # The sellers already exist in the CRM, so this must not read like the search failed.
        logger.exception("web_discovered_candidates_setup_failed", extra={"run_id": str(run_id)})
        names = ", ".join(c.org_name for c in outcome.created)
        return TrackedDiscovery(
            status="failed",
            message=(
                f"Created {len(outcome.created)} seller(s) in the CRM ({names}) but couldn't "
                "set them up for review. Find them in the CRM."
            ),
            notes=tuple(notes),
        )
    message = (
        f"Found {len(outcome.created)} new seller(s)."
        if outcome.created
        else "No new potential sellers found."
    )
    return TrackedDiscovery(status="done", message=message, notes=tuple(notes))
