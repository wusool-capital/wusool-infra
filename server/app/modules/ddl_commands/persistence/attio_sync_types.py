"""Return shapes of `attio_sync.py`'s `_organization_params`/`_person_params`/
`_deal_params`/`_buyer_role_params`/`_seller_role_params`/`_note_params` row
builders — one `TypedDict` per table, matching each field's actual
constructed type (the `attio.providers.attio.values` extraction helper it comes
from — `first`/`ref`/`actor` -> `str | None`, `titles` -> `list[str]`,
`boolean` -> `bool | None`, `number` -> `float | None`, `money` -> `dict |
None`, etc.), not necessarily the eventual Postgres column type after
SQLAlchemy/asyncpg coercion.

The `_*_batch_params` wrappers (`full_resync.py`'s batch path) mutate/
reshape a couple of these dicts field-by-field (`_deal_batch_params` even
pops `buyer_id`/`seller_id` for two different replacement keys) — genuinely
structural changes a `TypedDict` can't express as a mutation-in-place, so
those four stay `-> dict`, untyped.

The raw Attio API input these builders parse (`data: dict`) also stays
untyped — genuinely heterogeneous vendor JSON, already safely extracted
field-by-field via `attio.providers.attio.values`.
"""

from datetime import date, datetime
from typing import TypedDict

from app.modules.utilities.domain.json_types import JsonObject


class OrganizationParams(TypedDict):
    attio_id: str
    name: str
    description: str | None
    type: list[str]
    client_type: str | None
    sector_focus: list[str]
    stage_focus: list[str]
    geographic_focus: list[str]
    hq_country: str | None
    domains: list[str]
    categories: list[str]
    relationship_status: str | None
    connection_strength: str | None
    owner_attio_id: str | None
    last_interaction_at: datetime | None
    funding_raised: JsonObject | None
    estimated_arr: str | None
    raw_attio: JsonObject
    angellist: str | None
    facebook: str | None
    instagram: str | None
    twitter: str | None
    twitter_follower_count: int | None
    foundation_date: date | None
    ticket_size: str | None
    lead_source: str | None
    employee_range: str | None
    linkedin: str | None
    logo_url: str | None


class PersonParams(TypedDict):
    attio_id: str
    name: str
    role: str | None
    company_attio_id: str | None
    email: list[str]
    linkedin: str | None
    relationship_status: str | None
    connection_strength: str | None
    owner_attio_id: str | None
    last_interaction_at: datetime | None
    job_title: str | None
    contact_type: str | None
    phone: str | None
    avatar_url: str | None
    angellist: str | None
    facebook: str | None
    instagram: str | None
    twitter: str | None
    twitter_follower_count: int | None
    raw_attio: JsonObject


class DealParams(TypedDict):
    attio_id: str
    name: str
    stage: str | None
    stage_changed_at: datetime | None
    buyer_id: str | None
    seller_id: str | None
    owner_attio_id: str | None
    value: JsonObject | None
    teaser_status: str | None
    nda_count: int
    cim_ready: bool | None
    deal_memo_ready: bool | None
    contract_signed_date: date | None
    exclusivity_date: date | None
    data_room_substatus: str | None
    nda_status: str | None
    estimated_deal_value_usd: float | None
    expected_close_date: date | None
    fee: float | None
    assigned_advisor: list[str]
    deal_type: str | None
    universe_constructed: bool
    universe_size: int | None
    shortlist_approved: bool
    shortlist_size: int | None
    tier1_contacted: int | None
    responses: int | None
    counterparty_interested: int | None
    mandate_start_date: date | None
    mandate_expiry_date: date | None
    retainer_amount: JsonObject | None
    source_mandate_entry_id: str | None
    raw_attio: JsonObject


class BuyerRoleParams(TypedDict):
    org_attio_id: str
    model: str | None
    mandate_status: str | None
    ebitda_floor: JsonObject | None
    check_size_min: JsonObject | None
    check_size_max: JsonObject | None
    ev_ceiling: JsonObject | None
    deal_structure_tolerance: str | None
    earnout_tolerance: bool | None
    profitable_only: bool | None
    investment_strategy: str | None
    notes: str | None
    key_contact_attio_id: str | None
    acquisition_enrichment: str | None
    deals_introduced: int | None
    deals_converted: int | None
    ebitda_ceiling: JsonObject | None
    estimated_aum: JsonObject | None
    notable_investments: str | None
    key_personnel: str | None
    relationship_warmth: str | None
    target_geography: list[str]
    last_mandate_briefing_date: date | None
    prior_gcc_acquisition: str | None
    is_active: bool
    legacy_entry_id: str
    raw_attio: JsonObject


class SellerRoleParams(TypedDict):
    org_attio_id: str
    outreach_tier: str | None
    appetite_signal: str | None
    relationship_status: str | None
    est_revenue: JsonObject | None
    est_ebitda: JsonObject | None
    owner_salary: JsonObject | None
    valuation_low: JsonObject | None
    valuation_mid: JsonObject | None
    valuation_high: JsonObject | None
    sell_timeline: str | None
    readiness_score: float | None
    readiness_band: str | None
    last_attempt_date: date | None
    last_attempt_channel: str | None
    last_attempt_outcome: str | None
    lead_quality_score: float | None
    re_engage_date: date | None
    is_active: bool
    years_active: int | None
    funding_stage: str | None
    revenue_last_full_year: JsonObject | None
    revenue_year_before: JsonObject | None
    gross_margin_pct: float | None
    ebitda_deducts_salary: bool | None
    annual_rent_cost: JsonObject | None
    largest_customer_revenue_pct: float | None
    repeat_revenue_pct: float | None
    location_count: int | None
    legacy_entry_id: str
    raw_attio: JsonObject


class NoteParams(TypedDict):
    id: str
    organization_id: str | None
    person_id: str | None
    buyer_role_entry_id: str | None
    seller_role_entry_id: str | None
    note_type: str | None
    content: str | None
    created_at: datetime | None
