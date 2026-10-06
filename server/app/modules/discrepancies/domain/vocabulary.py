"""This module's own buyer-facing vocabulary — deliberately not
`matching_engine.domain.matching.scoring.CRITERION_REGISTRY`, which mixes
in seller-only criteria (`outreach_tier`, `appetite_signal`) this module
has no business touching. Keeps the dependency one-way: `discrepancies`
never imports `matching_engine`.
"""

from enum import StrEnum

from app.modules.discovery.domain.geography import TARGET_REGION_OPTIONS
from app.modules.lead_magnets.domain.shared.sector_options import (
    SECTOR_FOCUS_OPTIONS,
    SectorFocus,
)

# The live `sector_focus`/`target_vertical` options — reused rather than
# copied a third time; already drift-tested against Attio in
# `server/tests/test_sector_focus_vocabulary.py`.
VERTICAL_OPTIONS: frozenset[str] = SECTOR_FOCUS_OPTIONS

# Owned by `discovery`, which resolves these regions to countries.
REGION_OPTIONS: tuple[str, ...] = TARGET_REGION_OPTIONS

# The `target_country` options `ddl_commands.api.buyers`'s `BUYER_ROLE_FIELDS`
# declares — copied, not imported (`api` layer). Drift is caught by
# `server/tests/test_discrepancies_region_vocabulary.py`.
COUNTRY_OPTIONS: tuple[str, ...] = (
    "Algeria",
    "Argentina",
    "Armenia",
    "Australia",
    "Austria",
    "Azerbaijan",
    "Bahrain",
    "Bangladesh",
    "Barbados",
    "Belgium",
    "Bermuda",
    "Brazil",
    "British Virgin Islands",
    "Canada",
    "Cayman Islands",
    "China",
    "Croatia",
    "Cyprus",
    "Czechia",
    "Denmark",
    "Egypt",
    "Ethiopia",
    "Finland",
    "France",
    "Georgia",
    "Germany",
    "Ghana",
    "Gibraltar",
    "Greece",
    "Hong Kong",
    "Hungary",
    "Iceland",
    "India",
    "Indonesia",
    "Iran",
    "Iraq",
    "Ireland",
    "Israel",
    "Italy",
    "Japan",
    "Jersey",
    "Jordan",
    "Kazakhstan",
    "Kenya",
    "Kuwait",
    "Latvia",
    "Lebanon",
    "Libya",
    "Luxembourg",
    "Malaysia",
    "Malta",
    "Mexico",
    "Morocco",
    "Netherlands",
    "New Zealand",
    "Nicaragua",
    "Nigeria",
    "Norway",
    "Oman",
    "Pakistan",
    "Palestinian Authority",
    "Papua New Guinea",
    "Philippines",
    "Poland",
    "Portugal",
    "Qatar",
    "Romania",
    "Russia",
    "Saudi Arabia",
    "Serbia",
    "Sierra Leone",
    "Singapore",
    "Slovakia",
    "South Africa",
    "South Korea",
    "Spain",
    "Sri Lanka",
    "Sudan",
    "Sweden",
    "Switzerland",
    "Syria",
    "Taiwan",
    "Tanzania",
    "Thailand",
    "Trinidad and Tobago",
    "Tunisia",
    "Turkey",
    "Ukraine",
    "United Arab Emirates",
    "United Kingdom",
    "United States",
    "Vietnam",
    "Yemen",
)

# Hand-reviewed region pairs sharing no country; unlisted, nested or fuzzy pairs never conflict.
_DISJOINT_REGIONS: frozenset[frozenset[str]] = frozenset(
    frozenset(pair)
    for pair in (
        ("GCC", "Africa"),
        ("GCC", "Europe"),
        ("GCC", "Southeast Asia"),
        ("GCC", "Latin America"),
        ("MENA", "Europe"),
        ("MENA", "Southeast Asia"),
        ("MENA", "Latin America"),
        ("MENATP", "Southeast Asia"),
        ("MENATP", "Latin America"),
        ("Africa", "Asia"),
        ("Africa", "Europe"),
        ("Africa", "Southeast Asia"),
        ("Africa", "Latin America"),
        ("Asia", "Latin America"),
        ("Europe", "Southeast Asia"),
        ("Europe", "Latin America"),
        ("Southeast Asia", "Latin America"),
    )
)


def regions_disjoint(a: str, b: str) -> bool:
    return frozenset((a, b)) in _DISJOINT_REGIONS


def region_can_conflict(region: str) -> bool:
    return any(region in pair for pair in _DISJOINT_REGIONS)


# A generalist mandate covers every sector, so it never conflicts, like Global.
GENERALIST_VERTICAL: str = SectorFocus.DIVERSIFIED_GENERALIST.value


class Criterion(StrEnum):
    VERTICAL = "vertical"
    GEOGRAPHY = "geography"
    TICKET_BAND = "ticket_band"
    EBITDA = "ebitda"


# `/edit-buyer`'s field labels, so the advisor knows exactly which fields to fill in.
# Drift-tested against `BUYER_ROLE_FIELDS` in `tests/test_discrepancies_field_labels.py`.
CRITERION_FIELD_LABELS: dict[Criterion, tuple[str, ...]] = {
    Criterion.VERTICAL: ("Target vertical",),
    Criterion.GEOGRAPHY: ("Target region", "Target country"),
    Criterion.TICKET_BAND: ("Check size - min (USD)", "Check size - max (USD)"),
    Criterion.EBITDA: ("EBITDA floor (USD)", "EBITDA ceiling (USD)"),
}
