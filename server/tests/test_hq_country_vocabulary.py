"""`lead_magnets`' public valuation form and `ddl_commands`' Slack picker both
write `organizations.hq_country`, and they hold separate copies of the country
list — one in JavaScript, one in Python. #154 wired the form's "Geography / HQ"
select into the column; a country added there but not here silently stops
pre-selecting in `/edit-seller`/`/edit-buyer` (`multi_select_block` degrades to
a free-text box), so the divergence is invisible until an operator hits it.

Read as a file rather than imported: `ALL_GEOS` is browser JavaScript, and a
Python import across the module boundary would fail the architecture fitness
tests anyway.
"""

import re
from pathlib import Path

from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME

_ALL_GEOS_JS = (
    Path(__file__).resolve().parents[1] / "app/modules/lead_magnets/static/valuation/10-data.js"
)

# "Africa" is a region, not a country, and `organizations.region` now carries
# that vocabulary — so the picker deliberately does not offer it.
_NOT_A_COUNTRY = {"Africa"}


def _all_geos() -> set[str]:
    match = re.search(r"const ALL_GEOS = \[(.*?)\];", _ALL_GEOS_JS.read_text())
    assert match, f"ALL_GEOS not found in {_ALL_GEOS_JS}"
    return {g.strip().strip('"') for g in match.group(1).split(",")}


def test_picker_offers_every_country_the_valuation_form_can_send() -> None:
    options = set(ORGANIZATION_FIELDS_BY_NAME["hq_country"].options)
    missing = sorted(_all_geos() - _NOT_A_COUNTRY - options)
    assert not missing, (
        "the valuation form can write these to hq_country but the Slack picker "
        f"has no option for them: {missing}"
    )


def test_picker_still_has_room_under_slacks_option_cap() -> None:
    """The reason the list is a subset at all — see `api/organizations.py`."""
    assert len(ORGANIZATION_FIELDS_BY_NAME["hq_country"].options) <= 100
