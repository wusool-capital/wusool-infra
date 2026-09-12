"""Firecrawl implementation of `SearchPort`.

Bedrock cannot do web search for Claude at all, so the valuation tool's
comparables research is rebuilt around this: a cheap model plans the
queries, this runs them, and the main model reads the results.

Every failure degrades rather than breaks — a warning and an empty list, so
the caller falls back to static sector data instead of the visitor seeing an
error. Same posture as `matching_engine`'s own Firecrawl client. A missing
API key is one of those failures, not a startup error: local dev and the
Slack-bot-only path must still boot.

Signatures verified against the installed firecrawl-py 4.41.0 rather than
its docs: `search` is dispatched dynamically (it is absent from
`dir(AsyncFirecrawl)`), takes `query` plus `limit`/`sources`, and returns a
`SearchData` whose `.web` entries are `Document`s. Confirmed live against a
real account: `url`/`title`/`description` are never populated at the
top level on a `Document` — they only ever live on `item.metadata`
(a `DocumentMetadata`). Reading only the top-level attributes (the
original assumption here, and in this file's own tests) silently
produced an empty `url`/`title`/`snippet` for every single result.
"""

import logging

from firecrawl import AsyncFirecrawl

from app.modules.lead_magnets.domain.shared.search import SearchResult

logger = logging.getLogger(__name__)


class FirecrawlSearchClient:
    def __init__(self, api_key: str | None) -> None:
        self._client = AsyncFirecrawl(api_key=api_key) if api_key else None

    async def search(self, query: str, *, limit: int) -> list[SearchResult]:
        if self._client is None:
            logger.warning("firecrawl_search_skipped reason=no_api_key")
            return []

        try:
            data = await self._client.search(query, limit=limit, sources=["web"])
        except Exception as exc:  # noqa: BLE001 - degrade to the static fallback
            logger.warning("firecrawl_search_failed error=%s", exc, extra={"error": str(exc)})
            return []

        results = []
        for item in getattr(data, "web", None) or []:
            metadata = getattr(item, "metadata", None)
            results.append(
                SearchResult(
                    title=getattr(item, "title", None) or getattr(metadata, "title", None) or "",
                    url=getattr(item, "url", None) or getattr(metadata, "url", None) or "",
                    snippet=getattr(item, "description", None)
                    or getattr(metadata, "description", None)
                    or "",
                )
            )
        return results

    async def scrape(self, url: str) -> str:
        """Markdown text of one page. Empty string on any failure, so
        `/enrich` degrades to an honest "could not be fetched" rather than
        erroring — the model is instructed to return empty fields in that
        case instead of guessing from the company name.
        """
        if self._client is None:
            logger.warning("firecrawl_scrape_skipped reason=no_api_key")
            return ""

        try:
            document = await self._client.scrape(url, formats=["markdown"])
        except Exception as exc:  # noqa: BLE001 - degrade to an empty page
            logger.warning("firecrawl_scrape_failed error=%s", exc, extra={"error": str(exc)})
            return ""

        return getattr(document, "markdown", None) or ""
