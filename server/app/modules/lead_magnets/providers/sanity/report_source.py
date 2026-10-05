"""Sanity implementation of `ReportSourcePort`.

Page views read the CDN host, which has the Free plan's larger quota (1M
requests a month against the API host's 250k). The publish webhook reads the
uncached API host through `refresh`, because the CDN can still serve the old
document just after a publish.

Reads need no token: the dataset is public on the Free plan, and API
version 2025-02-19 defaults to the `published` perspective, so drafts never
leak. The one write, `save_rendered`, uses a write token. It stores the
flattened page in a hidden `renderedHtml` field. Readers only ever get that
field, never the pasted `html`: an unrendered bundle is a loader page whose
whole report sits in a script tag, so a report counts as published only once
it has been rendered. The webhook's filter ignores edits to `renderedHtml`,
so the write doesn't trigger a sync of its own.
"""

import json
import time

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report import ReportDocument, ReportSource

_API_VERSION = "v2025-02-19"
_CACHE_TTL_S = 300
# Unknown slugs are cached too, so the cache must be bounded against slug-scanning.
_CACHE_MAX = 512
_QUERY = (
    '*[_type == "report" && slug.current == $slug][0]{'
    '"slug": slug.current, title, "html": renderedHtml, "previewEnd": renderedPreviewEnd, '
    'excerpt, publishedAt, "updatedAt": _updatedAt, "coverUrl": cover.asset->url, '
    "featured, author, silo}"
)
_SOURCE_QUERY = '*[_type == "report" && slug.current == $slug][0]{_id, _rev, html, renderedFrom}'


class _SanityReport(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    slug: str
    title: str
    html: str | None = None
    preview_end: int | None = Field(default=None, alias="previewEnd")
    excerpt: str
    published_at: str | None = Field(default=None, alias="publishedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    cover_url: str | None = Field(default=None, alias="coverUrl")
    featured: bool | None = None
    author: str | None = None
    silo: str | None = None


class _QueryResponse(BaseModel):
    result: _SanityReport | None = None


class _SanitySource(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="_id")
    rev: str = Field(alias="_rev")
    html: str
    rendered_from: str | None = Field(default=None, alias="renderedFrom")


class _SourceResponse(BaseModel):
    result: _SanitySource | None = None


class _RenderedFields(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rendered_html: str = Field(alias="renderedHtml")
    rendered_preview_end: int = Field(alias="renderedPreviewEnd")
    rendered_from: str = Field(alias="renderedFrom")


class _Patch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    # Sanity rejects the patch (409) if the document moved on since it was read.
    if_revision_id: str = Field(alias="ifRevisionID")
    set_: _RenderedFields = Field(alias="set")


class _PatchMutation(BaseModel):
    patch: _Patch


class _Mutations(BaseModel):
    mutations: list[_PatchMutation]


class SanityReportSource:
    def __init__(
        self, *, project_id: str, dataset: str, write_token: str = "", timeout_s: float = 30.0
    ) -> None:
        path = f"/{_API_VERSION}/data/query/{dataset}"
        self._cdn_url = f"https://{project_id}.apicdn.sanity.io{path}"
        self._api_url = f"https://{project_id}.api.sanity.io{path}"
        self._mutate_url = (
            f"https://{project_id}.api.sanity.io/{_API_VERSION}/data/mutate/{dataset}"
        )
        self._write_token = write_token
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

    async def source(self, slug: str) -> ReportSource | None:
        response = await self._get(self._api_url, _SOURCE_QUERY, slug)
        doc = _SourceResponse.model_validate_json(response.content).result
        if doc is None:
            return None
        return ReportSource(
            document_id=doc.id, revision=doc.rev, html=doc.html, rendered_from=doc.rendered_from
        )

    async def save_rendered(
        self, source: ReportSource, *, html: str, preview_end: int, rendered_from: str
    ) -> bool:
        fields = _RenderedFields(
            rendered_html=html, rendered_preview_end=preview_end, rendered_from=rendered_from
        )
        patch = _Patch(id=source.document_id, if_revision_id=source.revision, set_=fields)
        body = _Mutations(mutations=[_PatchMutation(patch=patch)])
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                self._mutate_url,
                content=body.model_dump_json(by_alias=True),
                headers={
                    "Authorization": f"Bearer {self._write_token}",
                    "content-type": "application/json",
                },
            )
        if response.status_code == 409:
            return False
        response.raise_for_status()
        return True

    def _store(self, slug: str, report: ReportDocument | None) -> ReportDocument | None:
        self._cache.pop(slug, None)
        if len(self._cache) >= _CACHE_MAX:
            del self._cache[next(iter(self._cache))]  # oldest write first
        self._cache[slug] = (time.monotonic() + _CACHE_TTL_S, report)
        return report

    async def _get(self, url: str, query: str, slug: str) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(url, params={"query": query, "$slug": json.dumps(slug)})
        response.raise_for_status()
        return response

    async def _fetch(self, url: str, slug: str) -> ReportDocument | None:
        response = await self._get(url, _QUERY, slug)
        doc = _QueryResponse.model_validate_json(response.content).result
        if doc is None or doc.html is None or doc.preview_end is None:
            return None
        return ReportDocument(
            slug=doc.slug,
            title=doc.title,
            html=doc.html,
            preview_end=doc.preview_end,
            excerpt=doc.excerpt,
            published_at=doc.published_at,
            updated_at=doc.updated_at,
            cover_url=doc.cover_url,
            featured=bool(doc.featured),
            author=doc.author,
            silo=doc.silo,
        )
