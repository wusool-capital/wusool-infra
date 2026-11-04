"""Background body of a web find-match run: the match itself, then — when every
score is below `WEB_FALLBACK_MIN_SCORE` — discovery, the same follow-up Slack
runs get. Progress lands in `run_tracker` and the persisted rows; nothing is
posted to Slack.
"""

import logging
import uuid

from app.modules.matching_engine.api.dependencies import (
    RunDiscovery,
    discover_sellers_for_run,
    discovery_follows_match,
    open_matching_engine_service,
)
from app.modules.matching_engine.api.http.run_tracker import TrackedDiscovery, run_tracker
from app.modules.matching_engine.api.http.schemas import DiscoveryStatus
from app.modules.matching_engine.application.matching.use_cases import StartedRun
from app.modules.matching_engine.domain.buyers import BuyerContext

logger = logging.getLogger(__name__)


async def execute_web_run(
    started: StartedRun,
    buyer: BuyerContext,
    *,
    advisor_context: str | None,
    requested_by: str | None = None,
) -> None:
    run_tracker.set_executing(started.run_id, True)
    try:
        async with open_matching_engine_service() as service:
            # `execute_run` records its own failures on the run row.
            result = await service.execute_run(
                started, buyer, requested_by, advisor_context=advisor_context
            )
    finally:
        run_tracker.set_executing(started.run_id, False)
    run_tracker.set_notes(started.run_id, result.notes)

    if not discovery_follows_match(result):
        run_tracker.set_discovery(started.run_id, TrackedDiscovery(status="not_needed"))
        return
    await discover_for_web_run(started.run_id)


async def discover_for_web_run(run_id: uuid.UUID) -> None:
    """The web's report of `discover_sellers_for_run`, the same search Slack runs."""

    async def _running() -> None:
        run_tracker.set_discovery(run_id, TrackedDiscovery(status="running"))

    try:
        result = await discover_sellers_for_run(run_id, on_search_start=_running)
    except Exception:
        logger.exception("web_seller_discovery_failed", extra={"run_id": str(run_id)})
        result = RunDiscovery(kind="search_failed")
    if result.kind == "duplicate":
        # Another search holds the run; its progress or outcome is on the run row.
        run_tracker.clear_discovery(run_id)
        return
    run_tracker.set_discovery(run_id, _tracked(result))


def _tracked(result: RunDiscovery) -> TrackedDiscovery:
    status: DiscoveryStatus
    match result.kind:
        case "no_profile" | "no_terms":
            status = "skipped"
        case "unavailable":
            status = "unavailable"
        case "search_failed" | "setup_failed":
            status = "failed"
        case "done" | "duplicate":
            status = "done"
    return TrackedDiscovery(status=status, message=result.summary(), notes=result.notes)
