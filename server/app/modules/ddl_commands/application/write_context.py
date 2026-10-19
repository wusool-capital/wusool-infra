"""Who a seller/buyer write is on behalf of, handed to the write use cases so
they can record the activity in the same transaction as the Postgres write."""

from dataclasses import dataclass
from uuid import UUID

from app.modules.activities import ActivityActor, ActivitySource


@dataclass(frozen=True)
class WriteContext:
    actor: ActivityActor
    source: ActivitySource
    # The `command_runs` row this write belongs to; None when the ledger
    # write failed (it is best-effort) so the activity still records.
    command_run_id: UUID | None = None
