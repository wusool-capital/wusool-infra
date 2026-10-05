"""`discovery.domain.geography.TARGET_REGION_OPTIONS` and
`discrepancies.domain.vocabulary.COUNTRY_OPTIONS` are hand-transcribed
copies of `ddl_commands.api.buyers.BUYER_ROLE_FIELDS`'s `target_region` and
`target_country` options — necessary because a `domain/` layer must not
reach into `ddl_commands`' `api/` layer. A value renamed/added/removed in
one copy but not the other would silently break the geography conflict
check.

Unconstrained by the architecture fitness tests for the same reason
`test_sector_focus_vocabulary.py` already documents: a top-level test
importing both sides is outside `app/modules/**`.
"""

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.discovery.domain.geography import TARGET_REGION_OPTIONS
from app.modules.discrepancies.domain.vocabulary import COUNTRY_OPTIONS


def test_region_options_match_the_buyer_role_field_spec() -> None:
    live_options = set(BUYER_ROLE_FIELDS_BY_NAME["target_region"].options or ())
    assert set(TARGET_REGION_OPTIONS) == live_options


def test_country_options_match_the_buyer_role_field_spec() -> None:
    live_options = set(BUYER_ROLE_FIELDS_BY_NAME["target_country"].options or ())
    assert set(COUNTRY_OPTIONS) == live_options
