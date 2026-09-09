"""Retries whatever the write contract left unfinished.

The sweeper never spends money. `SubmissionService.complete` reuses any
stored AI output and, where a run's AI stage failed, resumes from the
deterministic fallback rather than calling Bedrock again. The per-class
retry ceilings live in the repository as one SQL CASE, so a row is never
even claimed past its own limit.

The timer and the session that drive this live in `bootstrap.py` — this
layer may not import `persistence/`, and keeping the loop out of here also
makes one pass directly testable.
"""

import logging
from datetime import UTC, datetime, timedelta

from app.modules.lead_magnets.application.ports import ToolRunsPort
from app.modules.lead_magnets.application.submit import SubmissionService

logger = logging.getLogger(__name__)


async def sweep_once(
    tool_runs: ToolRunsPort, submissions: SubmissionService, *, stale_after_s: int
) -> int:
    """One pass. Returns how many runs were resumed."""
    cutoff = datetime.now(UTC) - timedelta(seconds=stale_after_s)

    promoted = await tool_runs.promote_role_fks()
    if promoted:
        logger.info("lead_magnet_sweeper_promoted_role_fks count=%d", promoted)

    for run in await tool_runs.abandon_past_ceiling(cutoff=cutoff):
        # Past its ceiling and still unfinished: this one needs a human.
        logger.error(
            "lead_magnet_run_abandoned run_id=%s tool=%s attempts=%d stage=%s",
            run.id,
            run.tool,
            run.attempt_count,
            run.stage,
        )

    claimed = await tool_runs.claim_stale(cutoff=cutoff)
    for run in claimed:
        logger.info(
            "lead_magnet_sweeper_resuming run_id=%s tool=%s attempt=%d stage=%s",
            run.id,
            run.tool,
            run.attempt_count,
            run.stage,
        )
        await submissions.complete(run)
    return len(claimed)
