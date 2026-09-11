"""Buyer application field validation.

Attio rejects an undefined select option and the live relay only logs it, so
an unmapped value silently goes missing on every write. Two things prevent
that and both are tested here: the option counts match what was pulled live,
and an unmapped input raises rather than being dropped.
"""

import pytest

from app.modules.lead_magnets.domain.buyer_network.buyer_network import (
    ORGANIZATION_TYPE_OPTIONS,
    TARGET_GEOGRAPHY_OPTIONS,
    UnmappedOrgTypeError,
    UnmappedSectorFocusError,
    UnmappedTargetGeographyError,
    validate_org_type,
    validate_sector_focus,
    validate_target_geography,
)
from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS


def test_there_are_twenty_live_org_type_options() -> None:
    """Pulled live against DEV Wusool Capital 2026-09-10 (`companies`/`type`)."""
    assert len(ORGANIZATION_TYPE_OPTIONS) == 20


def test_there_are_seven_live_target_geography_options() -> None:
    """From `ddl_commands/api/buyers.py`'s `BUYER_ROLE_FIELDS`."""
    assert len(TARGET_GEOGRAPHY_OPTIONS) == 7


@pytest.mark.parametrize(
    ("validator", "known", "unknown", "error"),
    [
        (validate_org_type, "Family Office", "Hedge Fund", UnmappedOrgTypeError),
        (validate_target_geography, "UAE", "Egypt", UnmappedTargetGeographyError),
        (validate_sector_focus, "Retail / E-Commerce", "Fin tech", UnmappedSectorFocusError),
    ],
)
def test_a_known_value_passes_and_an_unknown_one_raises(validator, known, unknown, error) -> None:
    assert validator([known]) == [known]
    with pytest.raises(error):
        validator([unknown])


def test_sector_focus_reuses_the_same_live_set_every_other_tool_maps_onto() -> None:
    """No new vocabulary here — the form offers the live 85 titles directly,
    the same set `sector_mapping.py`'s targets are validated against."""
    assert validate_sector_focus(list(SECTOR_FOCUS_OPTIONS)) == list(SECTOR_FOCUS_OPTIONS)
