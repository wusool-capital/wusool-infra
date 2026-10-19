"""Who a seller/buyer write is on behalf of, handed to the write use cases so
they can record the activity in the same transaction as the Postgres write."""

from dataclasses import dataclass
from uuid import UUID

from app.modules.activities import ActivityActor, ActivitySource


@dataclass(frozen=True)
class WriteContext:
    actor: ActivityActor
    source: ActivitySource
    # None when the best-effort ledger write failed, so the activity still records.
    command_run_id: UUID | None = None
