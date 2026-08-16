"""Which `organizations` fields `/edit-seller`/`/edit-buyer` may edit, and
how — the field-picker, the dynamic form, and submission-extraction all read
from this one list, so there's exactly one place that decides eligibility.

Deliberately excluded (see plan.md Part C): `connection_strength`
(Attio-system-managed, never writable regardless of what the API permits),
`owner` (actor-reference type), `last_interaction_at`, and the multi-select
org fields other than `sector_focus` (`type`, `stage_focus`,
`geographic_focus`, `domains`, `categories`) — deferred, not built this pass.
`name` is shown as read-only context (the modal title), never editable here.
"""

from dataclasses import dataclass
from typing import Literal

# "bool_as_text" exists for exactly one field, `buyer_roles.earnout_tolerance`
# — a real boolean in Attio (same tri-state Yes/No/Not-set UI as `"bool"`,
# same `boolean(v, slug)` parser on the Attio-read side per
# `database/sync-postgres.ps1`), but a `text` column in Postgres, not
# `boolean` — a pre-existing schema anomaly, not something this bot
# introduced or is allowed to fix by changing the column type. Rendering and
# Attio-side serialization are identical to `"bool"`; only the Postgres
# write differs (stringified, see `ddl_commands/shared/attio/write_payload.py`).
FieldKind = Literal[
    "text", "multiline", "select", "multi_select_text", "currency", "date", "bool", "bool_as_text"
]


@dataclass(frozen=True)
class FieldSpec:
    name: str
    label: str
    kind: FieldKind
    options: tuple[str, ...] = ()


ORGANIZATION_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("description", "Description", "multiline"),
    FieldSpec("hq_country", "HQ country", "text"),
    FieldSpec(
        "sector_focus",
        "Sector focus (comma-separated)",
        "multi_select_text",
    ),
    FieldSpec(
        "client_type",
        "Client type",
        "select",
        options=(
            "Fundraising",
            "M&A",
            "IR & Governance Retainer",
            "Direct Investments",
            "Project",
            "Workshop",
            "Other",
            "Buy-Side",
            "Sell-Side",
        ),
    ),
    FieldSpec(
        "relationship_status",
        "Relationship status",
        "select",
        options=("Warm", "Cold", "Closed"),
    ),
    FieldSpec(
        "estimated_arr",
        "Estimated ARR",
        "select",
        options=(
            "$0-$1M",
            "$1M-$10M",
            "$10M-$50M",
            "$50M-$100M",
            "$100M-$250M",
            "$250M-$500M",
            "$500M-$1B",
            "$1B-$10B",
            "$10B+",
        ),
    ),
    FieldSpec("funding_raised", "Funding raised (USD)", "currency"),
)

ORGANIZATION_FIELDS_BY_NAME = {f.name: f for f in ORGANIZATION_FIELDS}
