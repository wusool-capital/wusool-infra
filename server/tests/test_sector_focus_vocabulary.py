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

from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.lead_magnets.domain.shared.sector_options import SECTOR_FOCUS_OPTIONS


def test_lead_magnets_sector_options_match_the_slack_pickers() -> None:
    picker_options = set(ORGANIZATION_FIELDS_BY_NAME["sector_focus"].options)
    assert SECTOR_FOCUS_OPTIONS == picker_options, (
        "lead_magnets.SECTOR_FOCUS_OPTIONS has drifted from "
        "ddl_commands.ORGANIZATION_FIELDS_BY_NAME['sector_focus'].options — "
        f"only in lead_magnets: {sorted(SECTOR_FOCUS_OPTIONS - picker_options)}, "
        f"only in the Slack picker: {sorted(picker_options - SECTOR_FOCUS_OPTIONS)}"
    )
