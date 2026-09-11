"""Which fields enrichment can propose for each role, and where each one
writes. Mirrors the vocabulary of `ddl_commands.api.schemas.FieldKind`
deliberately — this module must never import `ddl_commands` (the
dependency points the other way; see the package docstring), so the kinds
are redeclared here rather than shared.

Seller fields are read by `matching_engine.domain.matching.scoring
.CRITERION_REGISTRY` (`est_revenue`, `est_ebitda`, geography, sector) and
are publicly discoverable — buyer fields have no such scoring leverage
today (buyer criteria are LLM-extracted from the buyer's own free text),
so the buyer set below is smaller and ships after seller is proven out.
"""

from dataclasses import dataclass
from enum import StrEnum
from typing import Literal

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
    # for this field, not a user-facing string.
    prompt_hint: str


SELLER_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
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
        "description",
        "Description",
        "multiline",
        WriteTarget.ORGANIZATION,
        "A concise, factual one-paragraph description of what the company does.",
    ),
    EnrichableField(
        "hq_country",
        "HQ country",
        "text",
        WriteTarget.ORGANIZATION,
        "The country of the company's headquarters.",
    ),
    EnrichableField(
        "employee_range",
        "Employee range",
        "select",
        WriteTarget.ORGANIZATION,
        "One of Attio's fixed employee-count bands (e.g. '11-50').",
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
        "twitter",
        "Twitter",
        "text",
        WriteTarget.ORGANIZATION,
        "The company's Twitter/X profile URL, if any.",
    ),
)

BUYER_ENRICHABLE_FIELDS: tuple[EnrichableField, ...] = (
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
    ),
    EnrichableField(
        "prior_gcc_acquisition",
        "Prior GCC acquisition",
        "text",
        WriteTarget.BUYER_ROLE,
        "A prior acquisition the buyer made in the GCC region, if publicly known.",
    ),
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
