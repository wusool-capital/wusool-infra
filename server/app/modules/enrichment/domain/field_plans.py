"""Which fields enrichment can propose for each role, and where each one
writes. Mirrors the vocabulary of `ddl_commands.api.schemas.FieldKind`
deliberately — this module must never import `ddl_commands` (the
dependency points the other way; see the package docstring), so the kinds
are redeclared here rather than shared.

Seller fields are read by `matching_engine.domain.matching.scoring
.CRITERION_REGISTRY` (`est_revenue`, `est_ebitda`, geography, sector) and
are publicly discoverable — buyer *role* fields (`investment_strategy`,
`estimated_aum`, ...) have no such scoring leverage today (buyer criteria are
LLM-extracted from the buyer's own free text), so that part of the buyer set
is smaller and ships after seller is proven out.

`ORGANIZATION_ENRICHABLE_FIELDS` is declared once and folded into both
`SELLER_ENRICHABLE_FIELDS` and `BUYER_ENRICHABLE_FIELDS` below — a buyer's
and a seller's organization are the exact same `organizations` row shape, so
an org field enrichable for one is enrichable for the other by construction.
This is deliberate: `region` was originally added to the seller side only
and silently missing from the buyer side until caught in review — a single
shared tuple makes that class of drift structurally impossible instead of
relying on remembering to update both lists by hand.

Not every `ddl_commands`-editable field belongs here. Three categories are
deliberately excluded, and a field only earns a place below when it is a
public, third-party-verifiable fact about the company — never our own
records about it:

- **Internal CRM/ops state** — describes our relationship or process with
  the org/role, not a fact about it, so there is nothing "public" to research:
  `organizations.client_type`/`relationship_status`/`lead_source`;
  `buyer_roles.model`/`mandate_status`/`relationship_warmth`/`notes`/
  `last_mandate_briefing_date`; `seller_roles.outreach_tier`/
  `appetite_signal`/`relationship_status`/`sell_timeline`/`last_attempt_date`/
  `last_attempt_channel`/`last_attempt_outcome`/`re_engage_date`.
- **Lead Magnet questionnaire fields** (`seller_roles.revenue_last_full_year`,
  `revenue_year_before`, `gross_margin_pct`, `ebitda_deducts_salary`,
  `annual_rent_cost`, `largest_customer_revenue_pct`, `repeat_revenue_pct`) —
  self-reported by the founder for benchmark scoring; a public-web estimate
  silently overwriting a self-reported figure would corrupt that benchmark,
  the same ownership concern `ddl_commands.api.buyers`'s docstring already
  raises for `acquisition_enrichment`/`deals_introduced`/`deals_converted`.
- **Not `/edit-seller`/`/edit-buyer`-editable at all** (`organizations.type`/
  `stage_focus`/`geographic_focus`/`domains`/`categories`, every
  benchmark/`pct_*`/tool-output column on `seller_roles`) — enrichment
  reuses that same edit-form machinery end to end (a proposed value is
  reviewed and saved through the ordinary `OrganizationUpdate`/
  `SellerUpdate`/`BuyerUpdate` write path), so a field has to be editable
  there before it can be a candidate here at all.

`organizations.ticket_size` is left out as ambiguous rather than excluded on
principle: its meaning overlaps with `buyer_roles.check_size_min`/`_max`
(also added below) and it carries no docstring of its own to resolve that —
worth a data-engineer call before wiring it either way.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

from app.modules.enrichment.domain.employee_bands import EMPLOYEE_RANGE_OPTIONS

FieldKind = Literal[
    "text",
    "multiline",
    "select",
    "multi_select_text",
    "multi_select_as_text",
    "currency",
    "date",
    "bool",
    "number",
    "percent",
]


class WriteTarget(StrEnum):
    SELLER_ROLE = "seller_role"
    BUYER_ROLE = "buyer_role"
    ORGANIZATION = "organization"


@dataclass(frozen=True)
class EnrichableField:
    name: str
    label: str
    kind: FieldKind
    write_target: WriteTarget
    # Guidance folded into the extraction prompt — what "good" looks like
    # for this field, not a user-facing string. When `options` is non-empty,
    # it — not this hint — is the authoritative vocabulary folded into the
    # prompt (see `enrich._field_line`); the hint stays as extra guidance.
    prompt_hint: str
    # Fixed vocabulary for a `select`/`multi_select_text` field, mirroring
    # `ddl_commands.api.schemas.FieldSpec.options` — empty for every field
    # without one. Kept in sync with `ddl_commands`' own `FieldSpec.options`
    # by `tests/test_enrichment_field_vocabulary.py`, since this module must
    # never import `ddl_commands` to check directly.
    options: tuple[str, ...] = ()


# Shared between seller and buyer targets — see the module docstring.
ORGANIZATION_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
    EnrichableField(
        "description",
        "Description",
        "multiline",
        WriteTarget.ORGANIZATION,
        "A concise, factual one-paragraph description of what the company does.",
    ),
    EnrichableField(
        "hq_country",
        "HQ country",
        "multi_select_as_text",
        WriteTarget.ORGANIZATION,
        "The country of the company's headquarters, as its full English name "
        "('United Arab Emirates', not 'UAE' or 'AE'). Comma-separate only if the "
        "company is genuinely headquartered in more than one country.",
    ),
    EnrichableField(
        "region",
        "Region",
        "multi_select_as_text",
        WriteTarget.ORGANIZATION,
        "The macro region the company's HQ sits in (e.g. 'GCC', 'MENA', 'Europe', "
        "'North America'), one level above its HQ country — inferred from that "
        "country, not the region(s) it does business in.",
    ),
    EnrichableField(
        "sector_focus",
        "Sector focus",
        "multi_select_text",
        WriteTarget.ORGANIZATION,
        "The industry sector(s) the company operates in, from its own public "
        "description of its business.",
        options=(
            "Clinic",
            "Garage",
            "Legal Services",
            "Retail / E-Commerce",
            "Utilities",
            "Creative / Arts & Culture",
            "IT Services / Distribution",
            "Industrial Manufacturing",
            "Pharmaceuticals / Biotech",
            "Trade & Technical Services",
            "Packaging & Materials",
            "Telecom / Connectivity",
            "Residential / Commercial Real Estate",
            "Cybersecurity",
            "Sports & Wellness",
            "Beauty & Personal Care",
            "EdTech / Education",
            "Diversified / Generalist",
            "Steel / Metals / Mining",
            "Oil & Gas",
            "Impact / ESG / Sustainability",
            "Fintech",
            "Asset Management",
            "Agriculture / AgriTech",
            "Technology",
            "Logistics / 3PL / Freight",
            "Enterprise Software",
            "Banking / Commercial",
            "AI / ML",
            "Construction & Engineering",
            "Luxury / Fashion / Apparel",
            "Gaming / Metaverse",
            "Real Assets",
            "Dental / Specialist Clinics",
            "Private Credit / Debt",
            "Web3 / Blockchain / Digital Assets",
            "Energy Infrastructure",
            "Food Manufacturing / FoodTech",
            "Public Markets / Equities",
            "Aviation / Aircraft Leasing",
            "Chemicals & Petrochemicals",
            "Medical Education",
            "B2B Business Services",
            "Biotech / Longevity",
            "FemTech / Mental Health",
            "Electrical Equipment",
            "Medical Devices & Supplies",
            "HR / Human Capital",
            "Healthcare Services / Clinics",
            "Supply Chain / Distribution",
            "SaaS / Cloud",
            "Property Management / Proptech",
            "Private Equity",
            "Healthtech / Digital Health",
            "Renewable Energy / CleanTech",
            "FMCG / Consumer Goods",
            "Venture / Growth (Africa / MENA SME)",
            "Space / Deep Tech",
            "Media / Entertainment / Gaming",
            "Family Office / Wealth Management",
            "Consulting / Advisory",
            "Marketing / AdTech",
            "Venture Capital",
            "Real Estate Development",
            "Sharia-Compliant",
            "Semiconductors / Hardware",
            "Energy Storage / Services",
            "Shipping / Maritime",
            "Insurance / Insurtech",
            "Pet Care",
            "Consumer & Lifestyle Services",
            "Sovereign Wealth Fund",
            "Investment Banking / M&A Advisory",
            "Transportation",
            "Mobility",
            "Water / Waste Management",
            "Automotive",
            "Hospitality / Hotels / Tourism",
            "Food & Beverage / QSR",
            "Robotics / Automation",
            "Security Services",
            "Financial Services",
            "Aquaculture / Forestry",
            "Aerospace & Defense",
            "Nursery",
        ),
    ),
    EnrichableField(
        "estimated_arr",
        "Estimated ARR",
        "select",
        WriteTarget.ORGANIZATION,
        "The company's approximate annual recurring revenue band, if publicly "
        "stated or reasonably inferable from disclosed revenue figures.",
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
    EnrichableField(
        "funding_raised",
        "Funding raised (USD)",
        "currency",
        WriteTarget.ORGANIZATION,
        "Total funding raised to date in USD, if publicly disclosed (press "
        "coverage, a funding database, the company's own announcements).",
    ),
    EnrichableField(
        "employee_range",
        "Employee range",
        "select",
        WriteTarget.ORGANIZATION,
        "The company's approximate employee-count band, from its own stated or reported headcount.",
        options=EMPLOYEE_RANGE_OPTIONS,
    ),
    EnrichableField(
        "foundation_date",
        "Foundation date",
        "date",
        WriteTarget.ORGANIZATION,
        "The company's founding date, in ISO format.",
    ),
    EnrichableField(
        "linkedin",
        "LinkedIn",
        "text",
        WriteTarget.ORGANIZATION,
        "The company's LinkedIn profile URL.",
    ),
    EnrichableField(
        "logo_url",
        "Logo URL",
        "text",
        WriteTarget.ORGANIZATION,
        "A direct URL to the company's logo image, if publicly available.",
    ),
    EnrichableField(
        "angellist",
        "AngelList",
        "text",
        WriteTarget.ORGANIZATION,
        "The company's AngelList (Wellfound) profile URL, if any.",
    ),
    EnrichableField(
        "facebook",
        "Facebook",
        "text",
        WriteTarget.ORGANIZATION,
        "The company's Facebook page URL, if any.",
    ),
    EnrichableField(
        "instagram",
        "Instagram",
        "text",
        WriteTarget.ORGANIZATION,
        "The company's Instagram profile URL, if any.",
    ),
    EnrichableField(
        "twitter",
        "Twitter",
        "text",
        WriteTarget.ORGANIZATION,
        "The company's Twitter/X profile URL, if any.",
    ),
    EnrichableField(
        "twitter_follower_count",
        "Twitter follower count",
        "number",
        WriteTarget.ORGANIZATION,
        "The company's Twitter/X follower count, read directly off its public profile page.",
    ),
)

SELLER_ROLE_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
    EnrichableField(
        "est_revenue",
        "Est. revenue (USD)",
        "currency",
        WriteTarget.SELLER_ROLE,
        "Most recent full-year revenue in USD, from a public source (press, filings, "
        "company site). A bare number, no range.",
    ),
    EnrichableField(
        "est_ebitda",
        "Est. EBITDA (USD)",
        "currency",
        WriteTarget.SELLER_ROLE,
        "Most recent full-year EBITDA in USD, if disclosed anywhere public.",
    ),
    EnrichableField(
        "years_active",
        "Years active",
        "number",
        WriteTarget.SELLER_ROLE,
        "Years since founding, derived from a stated founding year.",
    ),
    EnrichableField(
        "location_count",
        "Location count",
        "number",
        WriteTarget.SELLER_ROLE,
        "Number of physical locations/branches the company operates.",
    ),
    EnrichableField(
        "funding_stage",
        "Funding stage",
        "select",
        WriteTarget.SELLER_ROLE,
        "The company's most recent funding stage, if publicly disclosed or "
        "reported (press coverage, a funding database).",
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
    EnrichableField(
        "valuation_low",
        "Valuation - low (USD)",
        "currency",
        WriteTarget.SELLER_ROLE,
        "The low end of a publicly reported valuation range for the company "
        "(e.g. from a funding round or acquisition report). Leave unset if "
        "only a single point valuation is reported — use `valuation_mid` for that.",
    ),
    EnrichableField(
        "valuation_mid",
        "Valuation - mid (USD)",
        "currency",
        WriteTarget.SELLER_ROLE,
        "The single most-likely or most recently reported valuation figure for "
        "the company in USD, if publicly disclosed.",
    ),
    EnrichableField(
        "valuation_high",
        "Valuation - high (USD)",
        "currency",
        WriteTarget.SELLER_ROLE,
        "The high end of a publicly reported valuation range for the company "
        "(e.g. from a funding round or acquisition report). Leave unset if "
        "only a single point valuation is reported — use `valuation_mid` for that.",
    ),
    EnrichableField(
        "owner_salary",
        "Owner salary (USD)",
        "currency",
        WriteTarget.SELLER_ROLE,
        "The founder/owner's salary drawn from the business, in USD, on the rare "
        "occasion this is publicly disclosed (e.g. press coverage of a small "
        "business). Never a guess from company size alone.",
    ),
)

BUYER_ROLE_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
    EnrichableField(
        "investment_strategy",
        "Investment strategy",
        "multiline",
        WriteTarget.BUYER_ROLE,
        "A concise summary of the buyer's stated investment thesis/strategy.",
    ),
    EnrichableField(
        "notable_investments",
        "Notable investments",
        "multiline",
        WriteTarget.BUYER_ROLE,
        "A short list of the buyer's publicly known past investments/acquisitions.",
    ),
    EnrichableField(
        "estimated_aum",
        "Estimated AUM (USD)",
        "currency",
        WriteTarget.BUYER_ROLE,
        "The buyer's assets under management in USD, if publicly disclosed.",
    ),
    EnrichableField(
        "target_geography",
        "Target geography",
        "multi_select_text",
        WriteTarget.BUYER_ROLE,
        "Countries/regions the buyer targets, from its own stated investment scope.",
        options=(
            "UAE",
            "KSA",
            "Kuwait",
            "Bahrain",
            "Qatar",
            "Oman",
            "GCC-wide",
            "Egypt",
            "Global",
        ),
    ),
    EnrichableField(
        "prior_gcc_acquisition",
        "Prior GCC acquisition",
        "text",
        WriteTarget.BUYER_ROLE,
        "A prior acquisition the buyer made in the GCC region, if publicly known.",
    ),
    EnrichableField(
        "deal_structure_tolerance",
        "Deal structure tolerance",
        "select",
        WriteTarget.BUYER_ROLE,
        "The type of deal structure the buyer is open to, from its own stated "
        "investment criteria (e.g. a fund site stating it only takes majority "
        "positions).",
        options=("Majority", "Minority", "Flexible", "Acquisition Financing"),
    ),
    EnrichableField(
        "ebitda_floor",
        "EBITDA floor (USD)",
        "currency",
        WriteTarget.BUYER_ROLE,
        "The minimum EBITDA the buyer requires in a target, in USD, from its "
        "own stated investment criteria.",
    ),
    EnrichableField(
        "check_size_min",
        "Check size - min (USD)",
        "currency",
        WriteTarget.BUYER_ROLE,
        "The buyer's minimum per-deal check size in USD, from its own stated investment criteria.",
    ),
    EnrichableField(
        "check_size_max",
        "Check size - max (USD)",
        "currency",
        WriteTarget.BUYER_ROLE,
        "The buyer's maximum per-deal check size in USD, from its own stated investment criteria.",
    ),
    EnrichableField(
        "ev_ceiling",
        "EV ceiling (USD)",
        "currency",
        WriteTarget.BUYER_ROLE,
        "The maximum enterprise value the buyer will consider for a target, in "
        "USD, from its own stated investment criteria.",
    ),
    EnrichableField(
        "ebitda_ceiling",
        "EBITDA ceiling (USD)",
        "currency",
        WriteTarget.BUYER_ROLE,
        "The maximum EBITDA the buyer will consider for a target, in USD, from "
        "its own stated investment criteria.",
    ),
)

SELLER_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
    SELLER_ROLE_ENRICHABLE_FIELDS + ORGANIZATION_ENRICHABLE_FIELDS
)
BUYER_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
    BUYER_ROLE_ENRICHABLE_FIELDS + ORGANIZATION_ENRICHABLE_FIELDS
)

_SELLER_FIELDS_BY_NAME = {f.name: f for f in SELLER_ENRICHABLE_FIELDS}
_BUYER_FIELDS_BY_NAME = {f.name: f for f in BUYER_ENRICHABLE_FIELDS}


def enrichable_fields_for(kind: str) -> tuple[EnrichableField, ...]:
    if kind == "seller":
        return SELLER_ENRICHABLE_FIELDS
    if kind == "buyer":
        return BUYER_ENRICHABLE_FIELDS
    raise ValueError(f"Unknown enrichment target kind: {kind!r}")


def enrichable_fields_by_name_for(kind: str) -> dict[str, EnrichableField]:
    if kind == "seller":
        return _SELLER_FIELDS_BY_NAME
    if kind == "buyer":
        return _BUYER_FIELDS_BY_NAME
    raise ValueError(f"Unknown enrichment target kind: {kind!r}")
