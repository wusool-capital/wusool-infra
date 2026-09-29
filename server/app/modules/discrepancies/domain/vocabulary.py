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

# Regions with no single-country meaning — a stated "Global" or "Emerging
# Markets" context never conflicts with any stored region.
_UNRESTRICTED_REGIONS = frozenset({"Global", "Emerging Markets"})


def is_unrestricted_region(region: str) -> bool:
    return region in _UNRESTRICTED_REGIONS


class Criterion(StrEnum):
    VERTICAL = "vertical"
    GEOGRAPHY = "geography"
    TICKET_BAND = "ticket_band"
    EBITDA = "ebitda"
