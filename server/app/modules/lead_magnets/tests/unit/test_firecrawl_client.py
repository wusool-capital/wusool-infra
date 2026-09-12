"""Firecrawl degrades, never breaks — the comparables pipeline falls back to
static sector data, so an empty list must reach the caller instead of an
exception. "Fallback fires with Firecrawl switched off" is the acceptance
test for this file.

`url`/`title`/`description` live on `item.metadata` in Firecrawl's real
response, never at the top level of a `Document` (confirmed live against a
real account) — the fakes below model that real shape, not the wrong
assumption this file used to test against.
"""

from app.modules.lead_magnets.domain.shared.search import SearchResult
from app.modules.lead_magnets.providers.firecrawl.client import FirecrawlSearchClient


class _Metadata:
    def __init__(self, url: str | None, title: str | None, description: str | None) -> None:
        self.url = url
        self.title = title
        self.description = description


class _Item:
    """`url`/`title`/`description` deliberately absent at the top level —
    matching the real `Document` shape, where they only ever live on
    `.metadata`.
    """

    def __init__(self, metadata: _Metadata) -> None:
        self.metadata = metadata


class _Data:
    def __init__(self, web) -> None:
        self.web = web


class _FakeInner:
    def __init__(self, result=None, raises=None) -> None:
        self.result = result
        self.raises = raises
        self.calls: list[tuple[str, int]] = []

    async def search(self, query, *, limit, sources):
        self.calls.append((query, limit))
        if self.raises:
            raise self.raises
        return self.result


async def test_no_api_key_returns_empty_rather_than_raising() -> None:
    assert await FirecrawlSearchClient(None).search("gcc fit-out comparables", limit=5) == []


async def test_flattens_web_results_reading_from_metadata() -> None:
    client = FirecrawlSearchClient("fc-test")
    item = _Item(_Metadata("https://a.example", "A Corp", "Revenue of ..."))
    client._client = _FakeInner(_Data([item]))

    results = await client.search("q", limit=3)

    assert len(results) == 1
    assert results[0].url == "https://a.example"
    assert results[0].title == "A Corp"
    assert results[0].snippet == "Revenue of ..."
    assert client._client.calls == [("q", 3)]


async def test_api_failure_degrades_to_empty() -> None:
    client = FirecrawlSearchClient("fc-test")
    client._client = _FakeInner(raises=RuntimeError("502 upstream"))
    assert await client.search("q", limit=3) == []


async def test_missing_fields_do_not_crash_the_flatten() -> None:
    """The vendor's own result objects are not guaranteed to populate every
    field; a missing description must not take the whole pipeline down."""
    client = FirecrawlSearchClient("fc-test")
    partial = _Item(_Metadata("https://b.example", "B Corp", None))
    client._client = _FakeInner(_Data([partial]))

    results = await client.search("q", limit=1)
    assert results[0].snippet == ""


async def test_absent_web_key_returns_empty() -> None:
    client = FirecrawlSearchClient("fc-test")
    client._client = _FakeInner(_Data(None))
    assert await client.search("q", limit=1) == []


async def test_a_result_with_no_metadata_at_all_does_not_crash() -> None:
    client = FirecrawlSearchClient("fc-test")
    item = _Item(metadata=None)
    client._client = _FakeInner(_Data([item]))

    results = await client.search("q", limit=1)

    assert results == [SearchResult(title="", url="", snippet="")]
