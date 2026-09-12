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

Attribute types below were verified live against the SOURCE Attio workspace
(2026-08-30) via `GET /v2/objects/organizations/attributes`, not inferred:
`ticket_size` is genuinely free text, while `lead_source` and
`employee_range` are `select` and carry the option lists below verbatim from
Attio. They had been guessed as `"text"`, which fails the Attio write with a
400 as soon as an operator actually fills one in — a bare string is not a
valid value for a select attribute.

`sector_focus`'s 85 option titles were pulled the same way (2026-09-01,
`GET /v2/objects/organizations/attributes/sector_focus/options`) and are
identical in the SOURCE and DEV workspaces. It had been the one field with
no option list, rendered as a free-text box — so a typo ("Fin tech") only
surfaced as an `OptionNotFoundError` after `ack()`, discarding everything
else the operator had filled in. Same for `buyer_roles.target_geography`.

`client_type` is `text` in SOURCE Attio (verified live 2026-09-08,
`GET /v2/objects/organizations/attributes/client_type`, options list empty).
It was declared `select` here, so every write raised `OptionNotFoundError`
before reaching Attio. It is `multi_select_as_text` instead: operators still
pick from the vocabulary below, but the picked titles are joined with ", "
into a bare string — the shape the read path already writes into the same
text column (`persistence/attio_sync.py`). The options below are therefore
this codebase's own list, not Attio's: the live-schema test can't verify
them, because a text attribute has none.

`hq_country` and `region` are both `text` in Attio and both
`multi_select_as_text` here, for the same reason as `client_type` — a fixed
vocabulary operators shouldn't retype, stored as a bare joined string. An org
can legitimately carry more than one (a holdco headquartered across two
jurisdictions), which is why neither is a single-value `select`.

`hq_country`'s titles are .NET `RegionInfo.EnglishName` strings, because that
is what wrote the existing column: the SOURCE migration maps Attio's
`primary_location` through `RegionInfo::new(country_code).EnglishName`
(`infrastructure/crm-sync/scripts/source-attio/_internal/objects.ps1`), so
picking any other spelling would stop matching the data already there. The
list is a deliberate subset — Slack caps a multi-select at 100 options and
there are ~250 countries — weighted to GCC/MENA and the financial centres
this desk actually sees. A country outside it is not lost: `multi_select_block`
degrades to the free-text box, which is why `extract_field_value` must read
that shape back.
"""

from datetime import date

from pydantic import BaseModel, Field

from app.modules.ddl_commands.api.schemas import FieldSpec


class OrganizationUpdate(BaseModel):
    description: str | None = Field(default=None, max_length=4000)
    hq_country: str | None = Field(default=None, max_length=1000)
    region: str | None = Field(default=None, max_length=300)
    sector_focus: list[str] | None = None
    client_type: str | None = Field(default=None, max_length=200)
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
    FieldSpec(
        "hq_country",
        "HQ country",
        "multi_select_as_text",
        options=(
            "United Arab Emirates",
            "Saudi Arabia",
            "Qatar",
            "Kuwait",
            "Bahrain",
            "Oman",
            "Egypt",
            "Jordan",
            "Lebanon",
            "Iraq",
            "Syria",
            "Yemen",
            "Palestinian Authority",
            "Israel",
            "Türkiye",
            "Iran",
            "Morocco",
            "Algeria",
            "Tunisia",
            "Libya",
            "Sudan",
            "Mauritania",
            "Djibouti",
            "Somalia",
            "Nigeria",
            "Kenya",
            "South Africa",
            "Ghana",
            "Ethiopia",
            "Tanzania",
            "Uganda",
            "Rwanda",
            "Senegal",
            "Côte d'Ivoire",
            "Mozambique",
            "Zambia",
            "India",
            "Pakistan",
            "Bangladesh",
            "Sri Lanka",
            "Singapore",
            "Malaysia",
            "Indonesia",
            "Thailand",
            "Vietnam",
            "Philippines",
            "China",
            "Hong Kong SAR",
            "Japan",
            "South Korea",
            "Taiwan",
            "Kazakhstan",
            "Uzbekistan",
            "Azerbaijan",
            "Georgia",
            "Armenia",
            "United Kingdom",
            "Ireland",
            "France",
            "Germany",
            "Switzerland",
            "Netherlands",
            "Luxembourg",
            "Belgium",
            "Spain",
            "Portugal",
            "Italy",
            "Austria",
            "Sweden",
            "Norway",
            "Denmark",
            "Finland",
            "Poland",
            "Czechia",
            "Greece",
            "Cyprus",
            "Malta",
            "Monaco",
            "Liechtenstein",
            "Romania",
            "Hungary",
            "Russia",
            "Ukraine",
            "United States",
            "Canada",
            "Mexico",
            "Brazil",
            "Argentina",
            "Chile",
            "Colombia",
            "Peru",
            "Panama",
            "Cayman Islands",
            "British Virgin Islands",
            "Bermuda",
            "Australia",
            "New Zealand",
        ),
    ),
    FieldSpec(
        "region",
        "Region",
        "multi_select_as_text",
        options=(
            "GCC",
            "MENA",
            "Levant",
            "North Africa",
            "Sub-Saharan Africa",
            "Europe",
            "North America",
            "Latin America",
            "South Asia",
            "Southeast Asia",
            "East Asia",
            "Central Asia",
            "Oceania",
            "Global",
        ),
    ),
    FieldSpec(
        "sector_focus",
        "Sector focus",
        "multi_select_text",
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
    FieldSpec(
        "client_type",
        "Client type",
        "multi_select_as_text",
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
