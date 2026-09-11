"""Real Firecrawl implementation of `ResearchClient` — general web search
plus page content, unlike `matching_engine`'s Google-Maps-only client
(that one answers "what sellers exist"; this one answers "what does the
public web say about this specific company"). Fails soft: any Firecrawl
error is logged and swallowed, returning `[]` rather than failing the
whole enrichment attempt.
"""

import logging

from firecrawl import AsyncFirecrawl

from app.modules.enrichment.application.ports.research import SourceDocument

logger = logging.getLogger(__name__)

_MAX_CONTENT_CHARS = 4000


class FirecrawlResearchClient:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncFirecrawl(api_key=api_key)

    async def search(self, query: str, *, limit: int) -> list[SourceDocument]:
        try:
            result = await self._client.search(
                query, limit=limit, scrape_options={"formats": ["markdown"]}
            )
        except Exception:
            logger.warning("enrichment_research_search_failed query=%s", query, exc_info=True)
            return []

        documents: list[SourceDocument] = []
        for item in getattr(result, "web", None) or []:
            content = (getattr(item, "markdown", None) or getattr(item, "description", None) or "")[
                :_MAX_CONTENT_CHARS
            ]
            url = getattr(item, "url", None)
            title = getattr(item, "title", None)
            if not url or not content:
                continue
            documents.append(SourceDocument(url=url, title=title or url, content=content))

        if len(documents) < limit:
            logger.info(
                "enrichment_research_search_thin query=%s requested=%d returned=%d",
                query,
                limit,
                len(documents),
            )
        return documents
