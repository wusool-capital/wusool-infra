"""Real Firecrawl implementation of `FirecrawlClient` using Google Maps only."""

import logging
import re
from urllib.parse import quote, unquote, urlsplit

from firecrawl import AsyncFirecrawl

from app.modules.matching_engine.domain.web_search import WebSourcedLead
from app.modules.matching_engine.providers.firecrawl.schemas import MapsExtraction

logger = logging.getLogger(__name__)

_PLACE_LINK_RE = re.compile(r"/maps/place/([^/]+)/")


def _is_google_maps_url(url: str) -> bool:
    parsed = urlsplit(url)
    hostname = (parsed.hostname or "").lower()
    is_google_host = hostname == "google.com" or hostname.endswith(".google.com")
    return parsed.scheme == "https" and is_google_host and parsed.path.startswith("/maps/")


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
        if not _is_google_maps_url(link):
            continue
        match = _PLACE_LINK_RE.search(link)
        if match and _normalize_name(unquote(match.group(1)).replace("+", " ")) == target:
            return link
    return None


class FirecrawlMapsClient:
    def __init__(self, api_key: str) -> None:
        self._client = AsyncFirecrawl(api_key=api_key)

    async def find_potential_sellers(
        self, *, industry: str, geography: str, limit: int
    ) -> list[WebSourcedLead]:
        query = f"{industry} companies {geography}".strip()

        leads = await self._scrape_maps(query, limit)
        return leads

    async def _scrape_maps(self, query: str, limit: int) -> list[WebSourcedLead]:
        url = f"https://www.google.com/maps/search/{quote(query)}"
        try:
            result = await self._client.scrape(
                url,
                formats=[{"type": "json", "schema": MapsExtraction.model_json_schema()}, "links"],
                timeout=60_000,
            )
        except Exception:
            logger.warning("firecrawl_maps_scrape_failed query=%s", query, exc_info=True)
            return []

        raw = getattr(result, "json", None) or {}
        try:
            extracted = MapsExtraction.model_validate(raw)
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
