"""`ExtractedContext.to_domain` — the provider boundary drops a vertical or
region outside the option lists, so an LLM guess never becomes a conflict.
"""

from app.modules.discrepancies.domain.criteria import ParsedContext
from app.modules.discrepancies.providers.bedrock.schemas import ExtractedContext


def test_off_list_vertical_and_region_are_dropped_amounts_pass_through() -> None:
    extracted = ExtractedContext(
        verticals=["pharma tech"],
        region="UAE",
        ticket_low_usd=5_000_000.0,
        ticket_high_usd=15_000_000.0,
        ebitda_low_usd=2_000_000.0,
    )

    assert extracted.to_domain() == ParsedContext(
        ticket_low=5_000_000.0, ticket_high=15_000_000.0, ebitda_low=2_000_000.0
    )


def test_listed_verticals_are_kept_off_list_ones_dropped() -> None:
    extracted = ExtractedContext(
        verticals=["Pharmaceuticals / Biotech", "biotech / longevity", "Garage-ish"],
        region="GCC",
    )

    assert extracted.to_domain() == ParsedContext(
        verticals=("Pharmaceuticals / Biotech", "Biotech / Longevity"), region="GCC"
    )


def test_option_case_is_normalized_to_the_canonical_string() -> None:
    assert ExtractedContext(region=" gcc ").to_domain().region == "GCC"
