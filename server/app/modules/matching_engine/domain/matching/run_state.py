"""A run's progress as the web app shows it, derived from the header row alone.

There is no RUNNING status in `match_results`: the header is written as
`GENERATED` with no `completed_at`, so "still running" means "not completed
yet". A run the process lost (a deploy or container restart mid-run) never
completes, so after a timeout it is reported as stale instead of running forever.
"""

from datetime import datetime, timedelta
from typing import Literal

RunState = Literal["running", "stale", "failed", "completed"]


def run_state(
    *,
    status: str,
    started_at: datetime,
    completed_at: datetime | None,
    now: datetime,
    stale_after: timedelta,
) -> RunState:
    if completed_at is None:
        return "stale" if now - started_at > stale_after else "running"
    return "failed" if status == "FAILED" else "completed"
