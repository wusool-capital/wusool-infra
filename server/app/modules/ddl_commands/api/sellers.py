"""Pydantic schemas at the seller concept's external/application boundary,
plus which `seller_roles` fields `/edit-seller` may edit and how — data
definitions only. Wiring lives in `dependencies.py`.

All nullable DB columns stay `X | None` here — no defaults invented, no
"Unknown" sentinel at this layer.

Field-spec section deliberately excludes (plan.md Part C): `readiness_band`
(zero options currently defined in DEV Attio — nothing to show in a
dropdown), `readiness_score`/`lead_quality_score` (ownership: both manual
and pipeline-written — needs the data engineer's confirmation before this
bot edits them, not this bot's own call). `intake_source` was dropped from
the table entirely (#53 — every populated value was the constant "Direct",
and `organizations.lead_source` already carries the signal), taking the only
gated field with it: `GATED_SELLER_ROLE_FIELDS` is empty now, and the
confirmation-checkbox machinery it drove is kept for the next write-once
field rather than deleted.

Attribute types and every option list below were verified live against the
DEV Attio workspace (2026-08-30) via `GET /v2/lists/seller_role/attributes`
and each attribute's `/options`. Two corrections came out of that:
`funding_stage` is a `select`, not free text (a bare string 400s on write),
and `last_attempt_channel` was missing Attio's "WhatsApp" option, so
operators had no way to record it.
"""

import uuid
from datetime import date

from pydantic import BaseModel, Field

from app.modules.ddl_commands.api.schemas import FieldSpec, OrganizationSummary


class SellerSummary(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    organization: OrganizationSummary
    outreach_tier: str | None = None
    relationship_status: str | None = None


class SellerUpdate(BaseModel):
    """Every field `/edit-seller`'s field-picker can offer — see
    `SELLER_ROLE_FIELDS` below for the authoritative eligibility list this
    must stay in sync with. Excluded on purpose: `mandate_id` (needs a
    mandate UUID, not a natural Slack input), `raw_attio`/timestamps
    (system-managed), `readiness_score`/`readiness_band`/
    `lead_quality_score` (ownership: both manual and pipeline-written, or
    zero Attio options defined — see plan.md Part C).

    Select-kind fields (`outreach_tier`, `appetite_signal`, etc.) are typed
    as plain `str` — the Slack UI itself only ever submits one of
    `field_spec.py`'s fixed option titles (`select_block`'s `static_select`
    has no free-text path), so a stricter enum-style check here would be
    redundant, not safer. Money fields are a bare `float` amount, not
    `{"amount", "currency"}` — currency is fixed per field now (see
    `ddl_commands/shared/attio/money.py`), never user input.
    """

    outreach_tier: str | None = Field(default=None, max_length=100)
    appetite_signal: str | None = Field(default=None, max_length=100)
    relationship_status: str | None = Field(default=None, max_length=100)
    sell_timeline: str | None = Field(default=None, max_length=100)
    last_attempt_date: date | None = None
    last_attempt_channel: str | None = Field(default=None, max_length=100)
    last_attempt_outcome: str | None = Field(default=None, max_length=500)
    re_engage_date: date | None = None
    est_revenue: float | None = None
    est_ebitda: float | None = None
    owner_salary: float | None = None
    valuation_low: float | None = None
    valuation_mid: float | None = None
    valuation_high: float | None = None
    years_active: int | None = None
    funding_stage: str | None = Field(default=None, max_length=100)
    revenue_last_full_year: float | None = None
    revenue_year_before: float | None = None
    gross_margin_pct: float | None = None
    ebitda_deducts_salary: bool | None = None
    annual_rent_cost: float | None = None
    largest_customer_revenue_pct: float | None = None
    repeat_revenue_pct: float | None = None
    location_count: int | None = None


SELLER_ROLE_FIELDS: tuple[FieldSpec, ...] = (
    FieldSpec(
        "outreach_tier",
        "Outreach tier",
        "select",
        options=("Archive", "Tier 1", "Tier 2", "Tier 3"),
    ),
    FieldSpec(
        "appetite_signal",
        "Appetite signal",
        "select",
        options=(
            "Expressed Interest Directly / Inbound Deal",
            "Listed on Business-for-Sale Platform",
            "No Signal",
            "Warm Introduction / Direct Outreach",
        ),
    ),
    FieldSpec(
        "relationship_status",
        "Relationship status",
        "select",
        options=(
            "Not Contacted",
            "Outreach Sent",
            "Positive Response",
            "Not Now",
            "No Response",
            "Referred Out",
            "Converted to Mandate",
        ),
    ),
    FieldSpec(
        "sell_timeline",
        "Sell timeline",
        "select",
        options=("Immediate", "Within 6 Months", "6-12 Months", "12-24 Months", "Not Selling"),
    ),
    FieldSpec("last_attempt_date", "Last attempt date", "date"),
    FieldSpec(
        "last_attempt_channel",
        "Last attempt channel",
        "select",
        options=("Email", "In Person", "Instagram DM", "LinkedIn InMail", "Phone", "WhatsApp"),
    ),
    FieldSpec(
        "last_attempt_outcome",
        "Last attempt outcome",
        "select",
        options=(
            "No Response",
            "Not Now",
            "Referred",
            "Responded Negatively",
            "Responded Positively",
        ),
    ),
    FieldSpec("re_engage_date", "Re-engage date", "date"),
    FieldSpec("est_revenue", "Est. revenue (USD)", "currency"),
    FieldSpec("est_ebitda", "Est. EBITDA (USD)", "currency"),
    FieldSpec("owner_salary", "Owner salary (USD)", "currency"),
    FieldSpec("valuation_low", "Valuation - low (USD)", "currency"),
    FieldSpec("valuation_mid", "Valuation - mid (USD)", "currency"),
    FieldSpec("valuation_high", "Valuation - high (USD)", "currency"),
    FieldSpec("years_active", "Years active", "number"),
    FieldSpec(
        "funding_stage",
        "Funding stage",
        "select",
        options=(
            "Bootstrapped",
            "Not Applicable",
            "Pre-Seed",
            "Seed",
            "Series A",
            "Series B",
            "Series C+",
        ),
    ),
    FieldSpec("revenue_last_full_year", "Revenue - last full year (USD)", "currency"),
    FieldSpec("revenue_year_before", "Revenue - year before (USD)", "currency"),
    FieldSpec("gross_margin_pct", "Gross margin %", "percent"),
    FieldSpec("ebitda_deducts_salary", "EBITDA deducts salary", "bool"),
    FieldSpec("annual_rent_cost", "Annual rent cost (USD)", "currency"),
    FieldSpec("largest_customer_revenue_pct", "Largest customer revenue %", "percent"),
    FieldSpec("repeat_revenue_pct", "Repeat revenue %", "percent"),
    FieldSpec("location_count", "Location count", "number"),
)

SELLER_ROLE_FIELDS_BY_NAME = {f.name: f for f in SELLER_ROLE_FIELDS}
GATED_SELLER_ROLE_FIELDS: frozenset[str] = frozenset()
