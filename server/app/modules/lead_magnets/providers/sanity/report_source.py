"""Sanity implementation of `ReportSourcePort`.

Page views read the CDN host, which has the Free plan's larger quota (1M
requests a month against the API host's 250k). The publish webhook reads the
uncached API host through `refresh`, because the CDN can still serve the old
document just after a publish.

No token: the dataset is public on the Free plan, and API version
2025-02-19 defaults to the `published` perspective, so drafts never leak.
"""

import json
import time

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report import ReportDocument

_API_VERSION = "v2025-02-19"
_CACHE_TTL_S = 300
_QUERY = (
    '*[_type == "report" && slug.current == $slug][0]{'
    '"slug": slug.current, title, html, excerpt, publishedAt, "updatedAt": _updatedAt, '
    '"coverUrl": cover.asset->url, featured, author, silo}'
)


class _SanityReport(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    slug: str
    title: str
    html: str
    excerpt: str
    published_at: str | None = Field(default=None, alias="publishedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    cover_url: str | None = Field(default=None, alias="coverUrl")
    featured: bool | None = None
    author: str | None = None
    silo: str | None = None


class _QueryResponse(BaseModel):
    result: _SanityReport | None = None


class SanityReportSource:
    def __init__(self, *, project_id: str, dataset: str, timeout_s: float = 10.0) -> None:
        path = f"/{_API_VERSION}/data/query/{dataset}"
        self._cdn_url = f"https://{project_id}.apicdn.sanity.io{path}"
        self._api_url = f"https://{project_id}.api.sanity.io{path}"
        self._timeout_s = timeout_s
        # ponytail: per-process cache; a webhook refreshes one worker, the TTL bounds the rest.
        self._cache: dict[str, tuple[float, ReportDocument | None]] = {}

    async def get(self, slug: str) -> ReportDocument | None:
        cached = self._cache.get(slug)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]
        # Misses are cached too, or every unknown slug would hit Sanity on each page view.
        return self._store(slug, await self._fetch(self._cdn_url, slug))

    async def refresh(self, slug: str) -> ReportDocument | None:
        return self._store(slug, await self._fetch(self._api_url, slug))

    def _store(self, slug: str, report: ReportDocument | None) -> ReportDocument | None:
        self._cache[slug] = (time.monotonic() + _CACHE_TTL_S, report)
        return report

    async def _fetch(self, url: str, slug: str) -> ReportDocument | None:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(url, params={"query": _QUERY, "$slug": json.dumps(slug)})
        response.raise_for_status()
        doc = _QueryResponse.model_validate_json(response.content).result
        if doc is None:
            return None
        return ReportDocument(
            slug=doc.slug,
            title=doc.title,
            html=doc.html,
            excerpt=doc.excerpt,
            published_at=doc.published_at,
            updated_at=doc.updated_at,
            cover_url=doc.cover_url,
            featured=bool(doc.featured),
            author=doc.author,
            silo=doc.silo,
        )
