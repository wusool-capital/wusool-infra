"""This module's own buyer-facing vocabulary — deliberately not
`matching_engine.domain.matching.scoring.CRITERION_REGISTRY`, which mixes
in seller-only criteria (`outreach_tier`, `appetite_signal`) this module
has no business touching. Keeps the dependency one-way: `discrepancies`
never imports `matching_engine`.
"""

from enum import StrEnum

from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS

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

# Region pairs that share no country. Any pair not listed counts as
# overlapping (never a conflict) — so Global/Emerging Markets, nesting
# (GCC in MENA in MENATP) and fuzzy borders (Africa/MENA, Asia/Europe via
# Turkey and Russia) stay silent. Hand-reviewed; extend only with clear cases.
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
