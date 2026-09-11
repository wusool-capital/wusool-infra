"""The Firecrawl seam. Faked in tests, implemented by
`providers/firecrawl/client.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.shared.search import SearchResult


class SearchPort(Protocol):
    async def search(self, query: str, *, limit: int) -> list[SearchResult]: ...

    async def scrape(self, url: str) -> str:
        """The page's text, or `""` if it could not be fetched.

        `/enrich` reads the one URL the visitor gave us, so there is nothing
        to search for — the live prompt's "use web search to find the
        company's website" was solving a problem that does not exist here.
        """
        ...
