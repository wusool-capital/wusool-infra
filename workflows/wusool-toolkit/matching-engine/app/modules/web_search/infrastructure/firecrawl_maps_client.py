"""Real Firecrawl implementation of `FirecrawlClient`. Primary path scrapes
a Google Maps search URL with a JSON extraction schema (confirmed live:
this actually works — real business name/address/category returned for a
"healthcare acquisition targets Saudi Arabia" query). Falls back to a plain
Firecrawl web search (title/url/description only, no address/category) if
the Maps scrape raises or returns nothing — never raises out of this
client, since a lead-finding fallback must not itself become the reason a
run fails; the caller treats an empty list as "no leads found."
"""

import logging
import re
from urllib.parse import quote, unquote

from firecrawl import AsyncFirecrawl
from pydantic import BaseModel

from app.modules.web_search.domain.firecrawl_client import WebSourcedLead

logger = logging.getLogger(__name__)

_PLACE_LINK_RE = re.compile(r"/maps/place/([^/]+)/")


def _normalize_name(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "", name.lower())


def _match_place_link(name: str, links: list[str]) -> str | None:
    """The search-results page's `json` extraction and its `links` list come
    from the same scrape but aren't correlated by Firecrawl — matched here by
    comparing each link's `/maps/place/<slug>/` segment against the
    business name, so "View Source" opens the specific listing rather than
    re-running the shared search query.
    """
    target = _normalize_name(name)
    for link in links:
        match = _PLACE_LINK_RE.search(link)
        if match and _normalize_name(unquote(match.group(1)).replace("+", " ")) == target:
            return link
    return None


class _Business(BaseModel):
    name: str
    address: str | None = None
    category: str | None = None


class _MapsExtraction(BaseModel):
    businesses: list[_Business]


class FirecrawlMapsClient:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncFirecrawl(api_key=api_key)

    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[WebSourcedLead]:
        query = f"{industry} companies {geography}".strip()

        leads = await self._scrape_maps(query, limit)
        if leads:
            return leads

        logger.info("firecrawl_maps_scrape_empty query=%s, falling back to search", query)
        return await self._search_fallback(query, limit)

    async def _scrape_maps(self, query: str, limit: int) -> list[WebSourcedLead]:
        url = f"https://www.google.com/maps/search/{quote(query)}"
        try:
            result = await self._client.scrape(
                url,
                formats=[{"type": "json", "schema": _MapsExtraction.model_json_schema()}, "links"],
                timeout=60_000,
            )
        except Exception:
            logger.warning("firecrawl_maps_scrape_failed query=%s", query, exc_info=True)
            return []

        raw = getattr(result, "json", None) or {}
        try:
            extracted = _MapsExtraction.model_validate(raw)
        except Exception:
            logger.warning("firecrawl_maps_scrape_unparseable query=%s raw=%s", query, raw)
            return []

        links = getattr(result, "links", None) or []
        return [
            WebSourcedLead(
                name=b.name,
                source_url=_match_place_link(b.name, links) or url,
                address=b.address,
                category=b.category,
            )
            for b in extracted.businesses[:limit]
        ]

    async def _search_fallback(self, query: str, limit: int) -> list[WebSourcedLead]:
        try:
            result = await self._client.search(query=query, limit=limit)
        except Exception:
            logger.warning("firecrawl_search_fallback_failed query=%s", query, exc_info=True)
            return []

        results = result.web or []
        leads = []
        for r in results[:limit]:
            url = getattr(r, "url", None)
            if not url:
                continue
            leads.append(
                WebSourcedLead(
                    name=getattr(r, "title", None) or url,
                    source_url=url,
                    snippet=getattr(r, "description", None),
                )
            )
        return leads
