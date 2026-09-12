"""`FirecrawlResearchClient.search` — the Firecrawl SDK call itself isn't
exercised here (mocked), but the metadata-fallback parsing is real,
end-to-end through the client's own method.

Regression coverage for a live bug: Firecrawl's real `Document` never
populates `url`/`title`/`description` at the top level — they only ever
live on `item.metadata` (confirmed live against a real account) — so
reading only the top-level attributes silently discarded every single
search result, every time, regardless of query quality.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from app.modules.enrichment.providers.firecrawl.client import FirecrawlResearchClient


def _metadata(*, url: str | None = None, title: str | None = None, description: str | None = None):
    return SimpleNamespace(url=url, title=title, description=description)


def _item(*, markdown: str | None = None, metadata=None, url=None, title=None) -> SimpleNamespace:
    return SimpleNamespace(markdown=markdown, metadata=metadata, url=url, title=title)


async def test_reads_url_and_title_from_metadata_not_the_top_level() -> None:
    """The exact live shape: top-level `url`/`title` are `None`, real
    values live on `item.metadata`."""
    client = FirecrawlResearchClient(api_key="test-key")
    client._client.search = AsyncMock(
        return_value=SimpleNamespace(
            web=[
                _item(
                    markdown="Mubadala is a sovereign investor...",
                    metadata=_metadata(
                        url="https://www.mubadala.com/en",
                        title="Mubadala Investment Company",
                    ),
                )
            ]
        )
    )

    docs = await client.search("Mubadala company profile", limit=5)

    assert len(docs) == 1
    assert docs[0].url == "https://www.mubadala.com/en"
    assert docs[0].title == "Mubadala Investment Company"
    assert "sovereign investor" in docs[0].content


async def test_falls_back_to_metadata_description_when_markdown_is_missing() -> None:
    client = FirecrawlResearchClient(api_key="test-key")
    client._client.search = AsyncMock(
        return_value=SimpleNamespace(
            web=[
                _item(
                    markdown=None,
                    metadata=_metadata(
                        url="https://example.com",
                        title="Example",
                        description="A short description.",
                    ),
                )
            ]
        )
    )

    docs = await client.search("query", limit=5)

    assert docs[0].content == "A short description."


async def test_top_level_url_wins_over_metadata_when_both_present() -> None:
    """Defensive fallback order: top-level attributes still win if a
    different response shape ever does populate them."""
    client = FirecrawlResearchClient(api_key="test-key")
    client._client.search = AsyncMock(
        return_value=SimpleNamespace(
            web=[
                _item(
                    markdown="content",
                    url="https://top-level.example.com",
                    title="Top Level Title",
                    metadata=_metadata(url="https://metadata.example.com", title="Metadata Title"),
                )
            ]
        )
    )

    docs = await client.search("query", limit=5)

    assert docs[0].url == "https://top-level.example.com"
    assert docs[0].title == "Top Level Title"


async def test_drops_a_result_with_no_url_anywhere() -> None:
    client = FirecrawlResearchClient(api_key="test-key")
    client._client.search = AsyncMock(
        return_value=SimpleNamespace(web=[_item(markdown="content", metadata=_metadata(url=None))])
    )

    docs = await client.search("query", limit=5)

    assert docs == []


async def test_drops_a_result_with_no_content_anywhere() -> None:
    client = FirecrawlResearchClient(api_key="test-key")
    client._client.search = AsyncMock(
        return_value=SimpleNamespace(
            web=[
                _item(
                    markdown=None,
                    metadata=_metadata(url="https://example.com", description=None),
                )
            ]
        )
    )

    docs = await client.search("query", limit=5)

    assert docs == []


async def test_content_is_truncated_to_max_chars() -> None:
    client = FirecrawlResearchClient(api_key="test-key")
    long_markdown = "a" * 5000
    client._client.search = AsyncMock(
        return_value=SimpleNamespace(
            web=[_item(markdown=long_markdown, metadata=_metadata(url="https://example.com"))]
        )
    )

    docs = await client.search("query", limit=5)

    assert len(docs[0].content) == 4000


async def test_search_failure_returns_empty_list() -> None:
    client = FirecrawlResearchClient(api_key="test-key")
    client._client.search = AsyncMock(side_effect=RuntimeError("boom"))

    docs = await client.search("query", limit=5)

    assert docs == []
