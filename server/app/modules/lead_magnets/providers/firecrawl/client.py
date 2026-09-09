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
`SearchData` whose `.web` entries carry `url`/`title`/`description`.
"""

import logging

from firecrawl import AsyncFirecrawl

from app.modules.lead_magnets.domain.search import SearchResult

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

        return [
            SearchResult(
                title=getattr(item, "title", None) or "",
                url=getattr(item, "url", None) or "",
                snippet=getattr(item, "description", None) or "",
            )
            for item in (getattr(data, "web", None) or [])
        ]
