"""Which `organizations` fields `/edit-seller`/`/edit-buyer` may edit, and
how — the field-picker, the dynamic form, and submission-extraction all read
from this one list, so there's exactly one place that decides eligibility.

Deliberately excluded (see plan.md Part C): `connection_strength`
(Attio-system-managed, never writable regardless of what the API permits),
`owner` (actor-reference type), `last_interaction_at`, and the multi-select
org fields other than `sector_focus` (`type`, `stage_focus`,
`geographic_focus`, `domains`, `categories`) — deferred, not built this pass.
`is_active` — bot-managed reconciliation state, set `True` explicitly by
`CreateSellerUseCase`/`CreateBuyerUseCase` on create, never
operator-editable. `name` is shown as read-only context (the modal title),
never editable here.

Attribute types below were verified live against the DEV Attio workspace
(2026-08-30) via `GET /v2/objects/organizations/attributes`, not inferred:
`ticket_size` is genuinely free text, while `lead_source` and
`employee_range` are `select` and carry the option lists below verbatim from
Attio. They had been guessed as `"text"`, which fails the Attio write with a
400 as soon as an operator actually fills one in — a bare string is not a
valid value for a select attribute.
"""

from dataclasses import dataclass
from typing import Literal

# A "bool_as_text" kind used to live here for `buyer_roles.earnout_tolerance`
# alone — boolean in Attio, `text` in Postgres. #53 made the column a real
# boolean, so the workaround and its stringify/parse round trip are gone.
#
# "number" vs "percent": both render a Slack `number_input` and pass through
# bare to Attio, but "number" maps to an `Integer` column and hard-casts to
# `int` (built for `twitter_follower_count`), while "percent" maps to
# `Numeric` and keeps decimal precision (e.g. `12.5`) for percentage-shaped
# columns like `seller_roles.gross_margin_pct`.
FieldKind = Literal[
    "text",
    "multiline",
    "select",
    "multi_select_text",
    "currency",
    "date",
    "bool",
    "number",
    "percent",
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
    FieldSpec("linkedin", "LinkedIn", "text"),
    FieldSpec("logo_url", "Logo URL", "text"),
    FieldSpec("angellist", "AngelList", "text"),
    FieldSpec("facebook", "Facebook", "text"),
    FieldSpec("instagram", "Instagram", "text"),
    FieldSpec("twitter", "Twitter", "text"),
    FieldSpec("twitter_follower_count", "Twitter follower count", "number"),
    FieldSpec("foundation_date", "Foundation date", "date"),
    FieldSpec("ticket_size", "Ticket size", "text"),
    FieldSpec("lead_source", "Lead source", "select", options=("Inbound", "Outbound")),
    FieldSpec(
        "employee_range",
        "Employee range",
        "select",
        options=(
            "1-10",
            "11-50",
            "51-250",
            "251-1K",
            "1K-5K",
            "5K-10K",
            "10K-50K",
            "50K-100K",
            "100K+",
        ),
    ),
)

ORGANIZATION_FIELDS_BY_NAME = {f.name: f for f in ORGANIZATION_FIELDS}
