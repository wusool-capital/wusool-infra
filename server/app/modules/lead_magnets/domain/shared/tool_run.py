"""The ledger's own vocabulary — no ORM, no vendor types.

`application/` works with these; `persistence/` maps them to and from the
`tool_runs` row. The two `Literal`s mirror live constraints: `ToolRunStatus`
is `tool_runs_status_check`, and `Tool` is the set `SCHEMA.md` documents.
Typing them means a typo fails at check time rather than as a Postgres
CHECK violation on a real submission.
"""

from dataclasses import dataclass
from typing import Literal, cast, get_args
from uuid import UUID

from app.modules.utilities.domain.json_types import JsonObject

ToolRunStatus = Literal["running", "succeeded", "failed", "abandoned"]
Tool = Literal[
    "valuation", "readiness", "benchmark", "buyer_network", "get_started", "attio_webhook"
]

# Which step of the write contract last completed. Persisted inside
# `payload` rather than as a column so a resume knows what it may skip —
# a run that already paid for its AI output must never pay twice.
# `email_confirmation`/`email_internal` are tracked separately, not as one
# `email` stage: a sweeper resume after the internal send fails must not
# re-send the visitor's confirmation, which already landed.
Stage = Literal["ai", "attio", "email_confirmation", "email_internal"]


class UnknownToolError(ValueError):
    pass


def parse_tool(raw: str) -> Tool:
    """`tool_runs.tool` is plain text with no CHECK behind it, unlike
    `status`. Validating on the way out keeps `Tool` honest rather than
    casting an unchecked string and hoping."""
    if raw not in get_args(Tool):
        raise UnknownToolError(f"unknown tool {raw!r} in tool_runs")
    return cast(Tool, raw)


@dataclass(frozen=True)
class ToolRunRecord:
    id: UUID
    tool: Tool
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
    # A buyer holds one role per vertical; `buyer_role_entry_id` is the first of these.
    buyer_role_entry_ids: tuple[str, ...] = ()
    # Not a `tool_runs` column, unlike the four above: this one is only ever
    # read back out of `payload.attio`, which is what makes a sweeper resume
    # skip the deal write. A row stored before this field existed simply
    # defaults it.
    deal_attio_id: str | None = None
    # Same as `deal_attio_id`: payload-only, used by the email stages to
    # link back to Attio. `None` whenever Attio's response omits it, or the
    # org write hit the patch path (an existing org matched by dedup, no
    # fresh `web_url` fetched for it).
    org_web_url: str | None = None
    deal_web_url: str | None = None
