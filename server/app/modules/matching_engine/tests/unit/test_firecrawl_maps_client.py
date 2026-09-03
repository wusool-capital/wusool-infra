"""Google Maps-only Firecrawl behavior and `_match_place_link`.

The helper matches a scraped business name against the Maps search page's
`links` list to find its specific listing URL, since Firecrawl's `json`
extraction and `links` format aren't correlated by position. No real
Firecrawl calls.
"""

from types import SimpleNamespace

import pytest

import app.modules.matching_engine.providers.firecrawl.client as maps_module  # noqa: E501
from app.modules.matching_engine.providers.firecrawl.client import (
    FirecrawlMapsClient,
    _match_place_link,
)

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


def test_rejects_non_google_maps_place_link() -> None:
    links = ["https://evil.example/maps/place/Japan+Renewable+Energy+Corp./data=!4m7"]

    assert _match_place_link("Japan Renewable Energy Corp.", links) is None


@pytest.mark.asyncio
async def test_empty_maps_scrape_does_not_fall_back_to_generic_web_search(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakeFirecrawl:
        def __init__(self, api_key: str) -> None:
            self.search_calls = 0

        async def scrape(self, url: str, **kwargs: object) -> SimpleNamespace:
            return SimpleNamespace(json={"businesses": []}, links=[])

        async def search(self, **kwargs: object) -> None:
            self.search_calls += 1
            raise AssertionError("generic web search must never be called")

    fake = FakeFirecrawl("test-key")
    monkeypatch.setattr(maps_module, "AsyncFirecrawl", lambda api_key: fake)
    client = FirecrawlMapsClient("test-key")

    leads = await client.find_potential_sellers(
        industry="healthcare", geography="Saudi Arabia", limit=3
    )

    assert leads == []
    assert fake.search_calls == 0
