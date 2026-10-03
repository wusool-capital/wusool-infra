"""`discrepancies.domain.vocabulary.REGION_OPTIONS` is a hand-transcribed
copy of `ddl_commands.api.buyers.BUYER_ROLE_FIELDS`'s `target_region`
options — necessary because `discrepancies`' `domain/` must not reach into
`ddl_commands`' `api/` layer. A region renamed/added/removed in one copy
but not the other would silently break the geography conflict check.

Unconstrained by the architecture fitness tests for the same reason
`test_sector_focus_vocabulary.py` already documents: a top-level test
importing both sides is outside `app/modules/**`.
"""

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.discrepancies.domain.vocabulary import REGION_OPTIONS


def test_region_options_match_the_buyer_role_field_spec() -> None:
    live_options = set(BUYER_ROLE_FIELDS_BY_NAME["target_region"].options or ())
    assert set(REGION_OPTIONS) == live_options
