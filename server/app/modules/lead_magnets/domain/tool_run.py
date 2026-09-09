"""The ledger's own vocabulary — no ORM, no vendor types.

`application/` works with these; `persistence/` maps them to and from the
`tool_runs` row. The two `Literal`s mirror live constraints: `ToolRunStatus`
is `tool_runs_status_check`, and `Tool` is the set `SCHEMA.md` documents.
Typing them means a typo fails at check time rather than as a Postgres
CHECK violation on a real submission.
"""

from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from app.modules.utilities.domain.json_types import JsonObject

ToolRunStatus = Literal["running", "succeeded", "failed", "abandoned"]
Tool = Literal["valuation", "readiness", "benchmark", "buyer_network", "attio_webhook"]

# Which step of the write contract last completed. Persisted inside
# `payload` rather than as a column so a resume knows what it may skip —
# a run that already paid for its AI output must never pay twice.
Stage = Literal["ai", "attio"]


@dataclass(frozen=True)
class ToolRunRecord:
    id: UUID
    tool: str
    status: str
    attempt_count: int
    payload: JsonObject
    stage: str | None


@dataclass(frozen=True)
class SubjectRefs:
    """What a completed Attio write knows about its subjects.

    The `*_name` fields exist because `tool_runs`' subject columns are
    foreign keys into the Postgres mirror, which does not have these rows
    yet at the moment the Attio write returns — `finish()` seeds a stub with
    the name so the FK is satisfiable, and the mirror's own upsert
    overwrites it seconds later. The role entry ids are Attio *list entry*
    ids, matching `seller_roles.legacy_entry_id`.
    """

    org_attio_id: str | None = None
    org_name: str | None = None
    person_attio_id: str | None = None
    person_name: str | None = None
    seller_role_entry_id: str | None = None
    buyer_role_entry_id: str | None = None
