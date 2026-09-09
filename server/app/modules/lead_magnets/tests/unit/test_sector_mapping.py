"""Tool sector value -> `organizations.sector_focus`.

Attio rejects an undefined select option and the live relay only logs it, so
an unmapped or misspelled sector silently goes missing on every write. Two
things prevent that and both are tested here: every target is a live option,
and an unmapped input raises rather than defaulting.
"""

import pytest

from app.modules.lead_magnets.domain.benchmark_dataset import SECTORS, TECH_SECTOR_LIST
from app.modules.lead_magnets.domain.sector_mapping import (
    BENCHMARK_SECTORS,
    UnmappedSectorError,
    to_sector_focus,
)
from app.modules.lead_magnets.domain.sector_options import SECTOR_FOCUS_OPTIONS


def test_there_are_eighty_five_live_options() -> None:
    """The count the handover documents state, confirmed against the repo's
    authoritative field spec."""
    assert len(SECTOR_FOCUS_OPTIONS) == 85


def test_every_mapping_target_is_a_live_option() -> None:
    """Also asserted at import, so a bad target is a startup failure. Kept
    here so the reason is visible in the suite."""
    unknown = sorted(t for t in BENCHMARK_SECTORS.values() if t not in SECTOR_FOCUS_OPTIONS)
    assert unknown == []


def test_every_benchmark_dropdown_value_is_mapped() -> None:
    """A value the form can produce but the mapping cannot translate would
    raise on a real submission."""
    unmapped = [s for s in list(SECTORS) + list(TECH_SECTOR_LIST) if s not in BENCHMARK_SECTORS]
    assert unmapped == []


@pytest.mark.parametrize(
    "value,expected",
    [
        ("contracting", "Construction & Engineering"),
        ("restaurant", "Food & Beverage / QSR"),
        ("nursery", "Nursery"),
        ("auto", "Garage"),
        ("itservices", "IT Services / Distribution"),
        ("travel", "Hospitality / Hotels / Tourism"),
        ("AI", "AI / ML"),
        ("SaaS", "SaaS / Cloud"),
        ("Proptech", "Property Management / Proptech"),
        ("Other", "Diversified / Generalist"),
    ],
)
def test_known_values_map(value: str, expected: str) -> None:
    assert to_sector_focus(value) == expected


def test_two_sources_may_share_one_target() -> None:
    """`salon` and `aesthetics` are both Beauty & Personal Care, and
    `grocery` and `ecommerce` both Retail / E-Commerce. Not a mistake."""
    assert to_sector_focus("salon") == to_sector_focus("aesthetics")
    assert to_sector_focus("grocery") == to_sector_focus("ecommerce")


def test_mobility_keeps_its_own_target() -> None:
    """The compound "Supply Chain or mobility" was split so a mobility
    business is not filed as distribution. Both targets are live options, so
    nothing needed creating in Attio."""
    assert to_sector_focus("Mobility") == "Mobility"
    assert to_sector_focus("Supply Chain") == "Supply Chain / Distribution"
    assert to_sector_focus("Mobility") != to_sector_focus("Supply Chain")


def test_the_pre_split_compound_still_maps() -> None:
    """Until the form ships the two separate options, a submission carrying
    the old label must not raise."""
    assert to_sector_focus("Supply Chain or mobility") == "Supply Chain / Distribution"


def test_an_option_title_passes_through() -> None:
    """`/enrich` picks from a list that overlaps the CRM's, so a value that
    is already an option needs no translation."""
    assert to_sector_focus("AI / ML") == "AI / ML"
    assert to_sector_focus("Fintech") == "Fintech"


def test_matching_is_whitespace_and_case_tolerant() -> None:
    assert to_sector_focus("  restaurant  ") == "Food & Beverage / QSR"
    assert to_sector_focus("RESTAURANT") == "Food & Beverage / QSR"
    assert to_sector_focus("ai / ml") == "AI / ML"


def test_an_unanswered_sector_is_not_an_error() -> None:
    assert to_sector_focus(None) is None
    assert to_sector_focus("") is None
    assert to_sector_focus("   ") is None


def test_an_unmapped_sector_raises_rather_than_defaulting() -> None:
    """A wrong sector is worse than a missing one: it silently misfiles the
    lead and skews any sector report built on it. So this must never quietly
    become "Diversified / Generalist"."""
    with pytest.raises(UnmappedSectorError) as excinfo:
        to_sector_focus("Vertical AI Applications")

    message = str(excinfo.value)
    assert "Vertical AI Applications" in message
    assert "Diversified" not in message.split("still unmapped")[0]
    # The message names where to add it and what is still outstanding.
    assert "sector_mapping.py" in message
    assert "valuation tool's ALL_SECTORS" in message


def test_the_valuation_vocabulary_is_still_unmapped_and_says_so() -> None:
    """214 of the valuation tool's 225 labels have no mapping. Recorded as a
    raise with a useful message rather than silently mis-filing them — the
    delivered `sector_mapping` artifact is still outstanding."""
    with pytest.raises(UnmappedSectorError):
        to_sector_focus("Blockchain & Crypto")
