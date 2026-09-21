"""`lead_magnets`' public valuation/benchmark forms and `ddl_commands`' Slack
picker both write `organizations.sector_focus`, and they hold separate
copies of its 85-option vocabulary — `lead_magnets.domain.shared
.sector_options.SectorFocus` is a hand-transcribed copy of
`ddl_commands.api.organizations.ORGANIZATION_FIELDS`'s `sector_focus`
`FieldSpec.options`, by necessity (`lead_magnets`' `domain/` must not
reach into `ddl_commands`' `api/` layer). A sector renamed/added/removed
in one copy but not the other is invisible until an operator hits it:
Attio rejects an undefined select value on write, and the live relay only
logs it — the sector silently fails to save.

Same pattern as `test_hq_country_vocabulary.py`, and unconstrained by the
architecture fitness tests for the same reason
`test_enrichment_field_vocabulary.py` already documents: a top-level test
importing both sides is outside `app/modules/**`, which is all
`test_architecture.py`'s `MODULES_ROOT` walks.
"""

import re
from pathlib import Path

from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS

_SCHEMA_PS1 = (
    Path(__file__).parents[2]
    / "infrastructure"
    / "crm-sync"
    / "scripts"
    / "source-attio"
    / "_internal"
    / "schema.ps1"
)


def _declared_options(slug: str, options_key: str) -> set[str]:
    """The option titles `schema.ps1` declares for one Attio attribute.

    Parsed rather than imported because the declaration lives in PowerShell.
    The block runs from `Slug="<slug>"` to that field's closing `); Config`.
    """
    text = _SCHEMA_PS1.read_text(encoding="utf-8")
    start = text.index(f'Slug="{slug}"')
    block_start = text.index(f"{options_key}=@(", start)
    block_end = text.index("); Config", block_start)
    return set(re.findall(r'"([^"]+)"', text[block_start:block_end]))


def test_attio_target_vertical_options_match_the_slack_picker() -> None:
    """`buyer_role.target_vertical` is the vertical re-grain's grain, seeded
    from a hardcoded `FixedOptions` list rather than from SOURCE: the option
    seeding pass for `buyer_role` reads SOURCE's `buyer_brain` LIST, while
    these titles live on the `companies` OBJECT, so pointing `SourceOption` at
    them would seed zero options and every write would fail silently.

    That hardcoding is what this pins. Attio rejects an undefined select value
    on write, so a sector present on the organization but missing here fails
    the backfill for every buyer in that vertical.
    """
    picker_options = set(ORGANIZATION_FIELDS_BY_NAME["sector_focus"].options)
    declared = _declared_options("target_vertical", "FixedOptions")
    assert declared == picker_options, (
        "schema.ps1's buyer_role.target_vertical FixedOptions has drifted from "
        "ddl_commands.ORGANIZATION_FIELDS_BY_NAME['sector_focus'].options — "
        f"only in schema.ps1: {sorted(declared - picker_options)}, "
        f"only in the Slack picker: {sorted(picker_options - declared)}"
    )


def test_attio_seller_sector_options_match_the_slack_picker() -> None:
    """`seller_role.sector` mirrors `organizations.sector_focus` in vocabulary
    and shape, but is declared as `TargetOptions` — and `seller_role` is the
    only entity whose option seeding PRUNES, archiving anything outside the
    declared set.

    So drift here is worse than elsewhere: a sector added to the organization
    vocabulary is not only missing from this dropdown, it is actively archived
    if anyone adds it by hand.
    """
    picker_options = set(ORGANIZATION_FIELDS_BY_NAME["sector_focus"].options)
    declared = _declared_options("sector", "TargetOptions")
    assert declared == picker_options, (
        "schema.ps1's seller_role.sector TargetOptions has drifted from "
        "ddl_commands.ORGANIZATION_FIELDS_BY_NAME['sector_focus'].options — "
        f"only in schema.ps1: {sorted(declared - picker_options)}, "
        f"only in the Slack picker: {sorted(picker_options - declared)}"
    )


def test_lead_magnets_sector_options_match_the_slack_pickers() -> None:
    picker_options = set(ORGANIZATION_FIELDS_BY_NAME["sector_focus"].options)
    assert SECTOR_FOCUS_OPTIONS == picker_options, (
        "lead_magnets.SECTOR_FOCUS_OPTIONS has drifted from "
        "ddl_commands.ORGANIZATION_FIELDS_BY_NAME['sector_focus'].options — "
        f"only in lead_magnets: {sorted(SECTOR_FOCUS_OPTIONS - picker_options)}, "
        f"only in the Slack picker: {sorted(picker_options - SECTOR_FOCUS_OPTIONS)}"
    )
