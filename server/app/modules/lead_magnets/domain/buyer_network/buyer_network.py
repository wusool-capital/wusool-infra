"""Buyer application field validation. Pure.

The form offers exactly Attio's own option titles for `organizations.type`
and `buyer_roles.target_geography` — unlike the benchmark/readiness sectors,
there is no tool-specific vocabulary to translate, only membership to check.
An unmapped value still **raises** rather than defaulting, for the same
reason `sector_mapping.py` does: a wrong option is worse than a missing one,
and Attio's own write only logs an unknown select value rather than failing
loudly.

`organizations.sector_focus` is the one field validated against a set
defined elsewhere (`domain/shared/sector_options.py`) rather than here: it
is the *same* live option set every other tool's sector maps onto, and this
form offers it directly as a multiselect rather than through a tool-specific
vocabulary, so there is nothing to translate — only the same membership
check `sector_mapping.py` already relies on.

`type`/`target_geography`'s option sets were pulled live against the DEV
Wusool Capital workspace (2026-09-10,
`mcp__attio__list-attribute-definitions` on `companies`/`type` and from
`ddl_commands/api/buyers.py`'s `BUYER_ROLE_FIELDS`, itself pulled live
2026-08-30) — not guessed.
"""

from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS

ORGANIZATION_TYPE_OPTIONS: frozenset[str] = frozenset(
    {
        "Startup",
        "Corporate Venture Capital",
        "Family Office",
        "Angel Syndicate",
        "Corporate",
        "Client: Advisory",
        "Fund of Fund",
        "Accelerator/Incubator",
        "Venture Builder",
        "Venture Capital",
        "Association",
        "Venture Debt",
        "Multi-Family Office",
        "Asset Management",
        "Search Fund",
        "Real Estate",
        "M&A Advisory",
        "Client: Sell-Side",
        "Roll-up",
        "Roll",
    }
)

TARGET_GEOGRAPHY_OPTIONS: frozenset[str] = frozenset(
    {"UAE", "KSA", "Kuwait", "Bahrain", "Qatar", "Oman", "GCC-wide"}
)


class UnmappedOrgTypeError(ValueError):
    pass


class UnmappedTargetGeographyError(ValueError):
    pass


class UnmappedSectorFocusError(ValueError):
    pass


def validate_org_type(values: list[str]) -> list[str]:
    for value in values:
        if value not in ORGANIZATION_TYPE_OPTIONS:
            raise UnmappedOrgTypeError(f"unknown organization type {value!r}")
    return values


def validate_target_geography(values: list[str]) -> list[str]:
    for value in values:
        if value not in TARGET_GEOGRAPHY_OPTIONS:
            raise UnmappedTargetGeographyError(f"unknown target geography {value!r}")
    return values


def validate_sector_focus(values: list[str]) -> list[str]:
    for value in values:
        if value not in SECTOR_FOCUS_OPTIONS:
            raise UnmappedSectorFocusError(f"unknown sector_focus {value!r}")
    return values
