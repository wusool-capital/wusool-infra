"""Tool sector value -> `organizations.sector_focus`.

Attio rejects an undefined select option and the live relay only logs it, so
an unmapped or misspelled sector silently goes missing on every write. Two
things prevent that and both are tested here: every target is a live option,
and an unmapped input raises rather than defaulting.
"""

import pytest

from app.modules.lead_magnets.domain.benchmark.benchmark_dataset import SECTORS, TECH_SECTOR_LIST
from app.modules.lead_magnets.domain.shared.sector_mapping import (
    _VALUATION_SECTORS_FOR_REVIEW,
    BENCHMARK_SECTORS,
    READINESS_SECTORS,
    VALUATION_SECTORS,
    UnmappedSectorError,
    to_sector_focus,
)
from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS
from app.modules.lead_magnets.domain.valuation.valuation_data import sectors as valuation_sectors

# `dopamine-readiness-score.html`'s `#cSector` — a real `<select>`, confirmed
# live 2026-09-10, transcribed separately from `READINESS_SECTORS`' own keys
# so a typo in one does not silently agree with the other.
_READINESS_DROPDOWN_VALUES = (
    "Technology & SaaS",
    "Healthcare & Medical",
    "F&B & Hospitality",
    "Professional Services",
    "Education & Training",
    "Retail & E-Commerce",
    "Construction & Contracting",
    "Logistics & Supply Chain",
    "Financial Services",
    "Manufacturing & Industrial",
    "Other",
)


def test_there_are_eighty_five_live_options() -> None:
    """The count the handover documents state, confirmed against the repo's
    authoritative field spec."""
    assert len(SECTOR_FOCUS_OPTIONS) == 85


def test_every_mapping_target_is_a_live_option() -> None:
    """Also asserted at import, so a bad target is a startup failure. Kept
    here so the reason is visible in the suite."""
    unknown = sorted(
        t
        for t in {**BENCHMARK_SECTORS, **READINESS_SECTORS, **VALUATION_SECTORS}.values()
        if t not in SECTOR_FOCUS_OPTIONS
    )
    assert unknown == []


def test_every_benchmark_dropdown_value_is_mapped() -> None:
    """A value the form can produce but the mapping cannot translate would
    raise on a real submission."""
    unmapped = [s for s in list(SECTORS) + list(TECH_SECTOR_LIST) if s not in BENCHMARK_SECTORS]
    assert unmapped == []


def test_every_readiness_dropdown_value_is_mapped() -> None:
    """A curl test against a throwaway DB found 10 of these 11 raising
    `UnmappedSectorError` before `READINESS_SECTORS` existed."""
    unmapped = [s for s in _READINESS_DROPDOWN_VALUES if s not in READINESS_SECTORS]
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


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Technology & SaaS", "SaaS / Cloud"),
        ("Healthcare & Medical", "Healthcare Services / Clinics"),
        ("F&B & Hospitality", "Food & Beverage / QSR"),
        ("Retail & E-Commerce", "Retail / E-Commerce"),
        ("Financial Services", "Financial Services"),
    ],
)
def test_readiness_known_values_map(value: str, expected: str) -> None:
    assert to_sector_focus(value) == expected


@pytest.mark.parametrize(
    "value,expected",
    [
        ("Automakers", "Automotive"),
        ("Artificial Intelligence", "AI / ML"),
        ("Blockchain & Crypto", "Web3 / Blockchain / Digital Assets"),
        ("Restaurants & Nightlife", "Food & Beverage / QSR"),
        ("Commercial Banking", "Banking / Commercial"),
        ("Metals & Mining", "Steel / Metals / Mining"),
    ],
)
def test_valuation_known_values_map(value: str, expected: str) -> None:
    assert to_sector_focus(value) == expected


def test_flagged_valuation_mappings_are_a_real_nonempty_subset() -> None:
    """`_VALUATION_SECTORS_FOR_REVIEW` names the judgment calls worth a
    second look, not the whole 204 — every one of them must be a real key
    in `VALUATION_SECTORS`, and there must be at least one (204 labels
    against an 85-option taxonomy always leaves genuine ambiguity)."""
    assert len(_VALUATION_SECTORS_FOR_REVIEW) > 0
    assert set(_VALUATION_SECTORS_FOR_REVIEW) <= set(VALUATION_SECTORS)


def test_readiness_and_benchmark_agree_on_shared_targets() -> None:
    """Both dropdowns independently offer sectors close enough to share a
    target — real agreement, not a coincidence to be surprised by."""
    assert to_sector_focus("Retail & E-Commerce") == to_sector_focus("ecommerce")
    assert to_sector_focus("Construction & Contracting") == to_sector_focus("contracting")
    assert to_sector_focus("Education & Training") == to_sector_focus("training")


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
    become "Diversified / Generalist". Not a real value from any tool's
    vocabulary — every real one now resolves."""
    with pytest.raises(UnmappedSectorError) as excinfo:
        to_sector_focus("Not A Real Sector Label")

    message = str(excinfo.value)
    assert "Not A Real Sector Label" in message
    assert "Diversified" not in message
    # The message names where to add it.
    assert "sector_mapping.py" in message


def test_every_valuation_label_is_now_mapped() -> None:
    """All 225 of `ALL_SECTORS` resolve: 21 already did (exact match or
    reused from `BENCHMARK_SECTORS`), `VALUATION_SECTORS` covers the other
    204."""
    unmapped = []
    for label in valuation_sectors():
        try:
            to_sector_focus(label)
        except UnmappedSectorError:
            unmapped.append(label)
    assert unmapped == []
    assert len(valuation_sectors()) == 225
    assert len(VALUATION_SECTORS) == 204
