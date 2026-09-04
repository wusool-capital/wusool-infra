"""Pydantic schema for the `organizations` fields `/edit-seller`/
`/edit-buyer`'s field-picker can offer, plus which fields may be edited and
how — data definitions only, mirroring `api/buyers.py`/`api/sellers.py`'s
own schemas + field-spec pattern.

`ORGANIZATION_FIELDS` is the authoritative eligibility list; the
field-picker, the dynamic form, and submission-extraction all read from
this one list, so there's exactly one place that decides eligibility, and
`OrganizationUpdate` must stay in sync with it.

Deliberately excluded (see plan.md Part C): `connection_strength`
(Attio-system-managed, never writable regardless of what the API permits),
`owner` (actor-reference type), `last_interaction_at`, and the multi-select
org fields other than `sector_focus` (`type`, `stage_focus`,
`geographic_focus`, `domains`, `categories`) — deferred, not built this pass.
`is_active` — bot-managed reconciliation state, set `True` explicitly by
`DdlCommandsService.create_seller`/`create_buyer` on create, never
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

from datetime import date

from pydantic import BaseModel, Field

from app.modules.ddl_commands.api.schemas import FieldSpec


class OrganizationUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    hq_country: str | None = Field(default=None, max_length=100)
    sector_focus: list[str] | None = None
    client_type: str | None = Field(default=None, max_length=100)
    relationship_status: str | None = Field(default=None, max_length=100)
    estimated_arr: str | None = Field(default=None, max_length=100)
    funding_raised: float | None = None
    linkedin: str | None = Field(default=None, max_length=500)
    logo_url: str | None = Field(default=None, max_length=500)
    angellist: str | None = Field(default=None, max_length=500)
    facebook: str | None = Field(default=None, max_length=500)
    instagram: str | None = Field(default=None, max_length=500)
    twitter: str | None = Field(default=None, max_length=500)
    twitter_follower_count: int | None = None
    foundation_date: date | None = None
    ticket_size: str | None = Field(default=None, max_length=100)
    lead_source: str | None = Field(default=None, max_length=100)
    employee_range: str | None = Field(default=None, max_length=100)


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
