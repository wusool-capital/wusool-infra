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

`ticket_size`, `lead_source`, and `employee_range` are given `"text"` kind
because their real Attio attribute type (free text vs. select) isn't
confirmed anywhere in this codebase — `attio_sync/upsert.py` reads them with
the same generic `v.first()` used for confirmed-`select` fields like
`client_type`, which doesn't disambiguate. `"text"` is the safe default: a
wrong guess at `select` options would silently misrepresent real Attio
categories, while a wrong guess at `"text"` instead fails loudly at the
Attio write if the attribute turns out to be `select`-typed.
"""

from dataclasses import dataclass
from typing import Literal

# A "bool_as_text" kind used to live here for `buyer_roles.earnout_tolerance`
# alone — boolean in Attio, `text` in Postgres. #53 made the column a real
# boolean, so the workaround and its stringify/parse round trip are gone.
FieldKind = Literal[
    "text", "multiline", "select", "multi_select_text", "currency", "date", "bool", "number"
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
    FieldSpec("lead_source", "Lead source", "text"),
    FieldSpec("employee_range", "Employee range", "text"),
)

ORGANIZATION_FIELDS_BY_NAME = {f.name: f for f in ORGANIZATION_FIELDS}
