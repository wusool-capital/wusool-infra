"""Pydantic schemas at the buyer concept's external/application boundary,
plus which `buyer_roles` fields `/edit-buyer` may edit and how — data
definitions only. Wiring lives in `dependencies.py`.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.

Field-spec section deliberately excludes (plan.md Part C):
`acquisition_enrichment`, `deals_introduced`, `deals_converted` (ownership:
both manual and pipeline-written — needs the data engineer's confirmation
before this bot edits them). `key_contact` deferred — a `record-reference`
type, not a plain field. `key_personnel` — intentionally not exposed. No
gated fields on the buyer side — nor on the seller side any more, since
`intake_source` was dropped in #53.

Attribute types verified live against the DEV Attio workspace (2026-08-30)
via `GET /v2/lists/buyer_role/attributes`: `prior_gcc_acquisition` is
genuinely free text, while `relationship_warmth` is a `select` and carries
Attio's own two options below. It had been guessed as `"text"`, which fails
the Attio write with a 400 once an operator fills it in.
"""

import uuid
from dataclasses import dataclass
from datetime import date

from pydantic import BaseModel, Field

from app.modules.ddl_commands.api.schemas import FieldSpec, OrganizationSummary
from app.modules.ddl_commands.application.buyers import ResolutionStatus


class BuyerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    model: str | None = None
    mandate_status: str | None = None


@dataclass(frozen=True)
class BuyerResolutionRead:
    status: ResolutionStatus
    candidates: list[BuyerSummary] | None = None


class BuyerUpdate(BaseModel):
    """Every field `/edit-buyer`'s field-picker can offer — see
    `BUYER_ROLE_FIELDS` below for the authoritative eligibility list this
    must stay in sync with. Excluded on purpose: `mandate_id`-equivalent
    (buyers have none), `key_contact` (a record-reference, deferred),
    `key_personnel` (intentionally not exposed), `raw_attio`/timestamps
    (system-managed), `acquisition_enrichment`/`deals_introduced`/
    `deals_converted` (ownership: both manual and pipeline-written — see
    plan.md Part C).

    Select-kind fields are typed as plain `str` — the Slack UI itself only
    ever submits one of `field_spec.py`'s fixed option titles. Money fields
    are a bare `float` amount — currency is fixed per field now, never user
    input (see `ddl_commands/shared/attio/money.py`). `earnout_tolerance` is
    a real `bool` column since #53 (`database/sync-postgres.ps1` parses it
    with the same `boolean()` function as `profitable_only`).
    """

    model: str | None = Field(default=None, max_length=100)
    mandate_status: str | None = Field(default=None, max_length=100)
    deal_structure_tolerance: str | None = Field(default=None, max_length=200)
    earnout_tolerance: bool | None = None
    profitable_only: bool | None = None
    investment_strategy: str | None = Field(default=None, max_length=2000)
    notes: str | None = Field(default=None, max_length=4000)
    ebitda_floor: float | None = None
    check_size_min: float | None = None
    check_size_max: float | None = None
    ev_ceiling: float | None = None
    ebitda_ceiling: float | None = None
    estimated_aum: float | None = None
    notable_investments: str | None = Field(default=None, max_length=2000)
    relationship_warmth: str | None = Field(default=None, max_length=100)
    target_geography: list[str] | None = None
    last_mandate_briefing_date: date | None = None
    prior_gcc_acquisition: str | None = Field(default=None, max_length=100)


BUYER_ROLE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec("model", "Model", "select", options=("Model 1 (Network)", "Model 2 (Full Mandate)")),
    FieldSpec(
        "mandate_status",
        "Mandate status",
        "select",
        options=("Active", "Paused", "Completed", "Dormant"),
    ),
    FieldSpec(
        "deal_structure_tolerance",
        "Deal structure tolerance",
        "select",
        options=("Majority", "Minority", "Flexible", "Acquisition Financing"),
    ),
    FieldSpec("earnout_tolerance", "Earnout tolerance", "bool"),
    FieldSpec("profitable_only", "Profitable only", "bool"),
    FieldSpec("investment_strategy", "Investment strategy", "multiline"),
    FieldSpec("notes", "Notes", "multiline"),
    FieldSpec("ebitda_floor", "EBITDA floor (USD)", "currency"),
    FieldSpec("check_size_min", "Check size - min (USD)", "currency"),
    FieldSpec("check_size_max", "Check size - max (USD)", "currency"),
    FieldSpec("ev_ceiling", "EV ceiling (USD)", "currency"),
    FieldSpec("ebitda_ceiling", "EBITDA ceiling (USD)", "currency"),
    FieldSpec("estimated_aum", "Estimated AUM (USD)", "currency"),
    FieldSpec("notable_investments", "Notable investments", "multiline"),
    FieldSpec("relationship_warmth", "Relationship warmth", "select", options=("Warm", "Cold")),
    FieldSpec("target_geography", "Target geography (comma-separated)", "multi_select_text"),
    FieldSpec("last_mandate_briefing_date", "Last mandate briefing date", "date"),
    FieldSpec("prior_gcc_acquisition", "Prior GCC acquisition", "text"),
)

BUYER_ROLE_FIELDS_BY_NAME = {f.name: f for f in BUYER_ROLE_FIELDS}
GATED_BUYER_ROLE_FIELDS: frozenset[str] = frozenset()
