"""This module's own buyer-facing vocabulary — deliberately not
`matching_engine.domain.matching.scoring.CRITERION_REGISTRY`, which mixes
in seller-only criteria (`outreach_tier`, `appetite_signal`) this module
has no business touching. Keeps the dependency one-way: `discrepancies`
never imports `matching_engine`.
"""

from enum import StrEnum

from app.modules.lead_magnets.domain.shared.sector_options import (
    SECTOR_FOCUS_OPTIONS,
    SectorFocus,
)

# The live `sector_focus`/`target_vertical` options — reused rather than
# copied a third time; already drift-tested against Attio in
# `server/tests/test_sector_focus_vocabulary.py`.
VERTICAL_OPTIONS: frozenset[str] = SECTOR_FOCUS_OPTIONS

# The same 10-option `target_region` list `ddl_commands.api.buyers`'s
# `BUYER_ROLE_FIELDS` declares — copied, not imported (`ddl_commands` is
# `api`-layer, off limits to this module's `domain`). Drift is caught by
# `server/tests/test_discrepancies_region_vocabulary.py`.
REGION_OPTIONS: tuple[str, ...] = (
    "GCC",
    "MENA",
    "MENATP",
    "Africa",
    "Asia",
    "Europe",
    "Southeast Asia",
    "Latin America",
    "Emerging Markets",
    "Global",
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


# Display wording for the advisor-facing message; enum values stay snake_case.
CRITERION_LABELS: dict[Criterion, str] = {
    Criterion.VERTICAL: "vertical",
    Criterion.GEOGRAPHY: "geography",
    Criterion.TICKET_BAND: "ticket band",
    Criterion.EBITDA: "EBITDA",
}
