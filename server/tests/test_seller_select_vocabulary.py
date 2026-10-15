"""`matching_engine`'s copy of the seller select options must match the live specs.

Lives outside `app/modules/**` so the architecture fitness tests don't see the
cross-module import, same as `test_sector_focus_vocabulary.py`.
"""

from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.matching_engine.domain.matching.seller_options import SELLER_SELECT_OPTIONS


def test_seller_select_options_match_the_field_specs() -> None:
    for name, options in SELLER_SELECT_OPTIONS.items():
        assert set(options) == set(SELLER_ROLE_FIELDS_BY_NAME[name].options)
