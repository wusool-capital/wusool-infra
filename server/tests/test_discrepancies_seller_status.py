"""`discrepancies.domain.vocabulary.SELLER_STATUS_OPTIONS` copies the seller
select options `matching_engine` scores on, by hand, since modules can't import
each other's domains. A drifted option would be echoed as a status the match
then drops.
"""

from app.modules.discrepancies.domain.vocabulary import SELLER_STATUS_OPTIONS
from app.modules.matching_engine.domain.matching.seller_options import SELLER_SELECT_OPTIONS


def test_status_options_match_the_matching_engines_seller_options() -> None:
    live = {option for options in SELLER_SELECT_OPTIONS.values() for option in options}
    assert set(SELLER_STATUS_OPTIONS) == live
