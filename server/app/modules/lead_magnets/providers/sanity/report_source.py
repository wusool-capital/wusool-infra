"""Sanity implementation of `ReportSourcePort`.

Reads the uncached `api.sanity.io` host rather than the CDN: the CDN can
still serve the old document just after a publish, and the in-process cache
below already keeps request volume far inside the Free plan's quota.

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
        self._url = f"https://{project_id}.api.sanity.io/{_API_VERSION}/data/query/{dataset}"
        self._timeout_s = timeout_s
        # ponytail: per-process cache; a webhook clears one worker, the TTL bounds the rest.
        self._cache: dict[str, tuple[float, ReportDocument | None]] = {}

    async def get(self, slug: str) -> ReportDocument | None:
        cached = self._cache.get(slug)
        if cached is not None and cached[0] > time.monotonic():
            return cached[1]
        report = await self._fetch(slug)
        # Misses are cached too, or every unknown slug would hit Sanity on each page view.
        self._cache[slug] = (time.monotonic() + _CACHE_TTL_S, report)
        return report

    def invalidate(self, slug: str) -> None:
        self._cache.pop(slug, None)

    async def _fetch(self, slug: str) -> ReportDocument | None:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(
                self._url, params={"query": _QUERY, "$slug": json.dumps(slug)}
            )
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
