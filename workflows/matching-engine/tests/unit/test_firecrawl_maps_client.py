"""`_match_place_link` — matching a scraped business name against the
Maps search page's `links` list to find its specific listing URL, since
Firecrawl's `json` extraction and `links` format aren't correlated by
position. No real Firecrawl calls.
"""

from app.modules.web_search.infrastructure.firecrawl_maps_client import _match_place_link

_LINKS = [
    "https://www.google.com/maps/place/Japan+Renewable+Energy+Corp./data=!4m7!3m6",
    "https://www.google.com/maps/place/Vector+Renewables+Japan+K.K./data=!4m7!3m6",
    "https://www.google.com/search?q=unrelated",
]


def test_matches_by_normalized_name() -> None:
    link = _match_place_link("Japan Renewable Energy Corp.", _LINKS)
    assert link == _LINKS[0]


def test_matches_regardless_of_punctuation_spacing() -> None:
    link = _match_place_link("vector renewables japan k k", _LINKS)
    assert link == _LINKS[1]


def test_returns_none_when_no_match() -> None:
    assert _match_place_link("Some Other Company", _LINKS) is None
