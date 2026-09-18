"""Get Started form field validation. Pure.

The form offers exactly Attio's own option titles for `seller_role`'s
`sell_timeline` — like the buyer form's `type`/`target_geography`, there is
no tool-specific vocabulary to translate, only membership to check. Sector
is the exception and goes through `domain/shared/sector_mapping.py`'s
`GET_STARTED_SECTORS` instead, because that form dropdown is this tool's own
9-value wording rather than the CRM's.

An unmapped value **raises** rather than defaulting, for the same reason
`sector_mapping.py` does: Attio's own write only logs an unknown select
value rather than failing loudly, so a wrong option would silently drop the
timeline on every submission.

`sell_timeline`'s option set was pulled live against the Wusool Capital
workspace (2026-09-13) and matches `ddl_commands/api/sellers.py`'s own
`FieldSpec` for the same column — not guessed.
"""

SELL_TIMELINE_OPTIONS: frozenset[str] = frozenset(
    {"Immediate", "Within 6 Months", "6-12 Months", "12-24 Months", "Not Selling"}
)


class UnmappedSellTimelineError(ValueError):
    pass


def validate_sell_timeline(value: str) -> str:
    if value not in SELL_TIMELINE_OPTIONS:
        raise UnmappedSellTimelineError(f"unknown sell timeline {value!r}")
    return value
