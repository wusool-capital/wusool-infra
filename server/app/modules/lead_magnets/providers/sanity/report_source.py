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
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report import (
    LostPins,
    Pin,
    ReportDocument,
    ReportSource,
)
from app.modules.lead_magnets.providers.sanity.images import resized
from app.modules.lead_magnets.providers.sanity.portable_text import Block, rich_report

# Shared with `article_source.py`; the webhook is pinned to the same version.
API_VERSION = "v2025-02-19"
_CACHE_TTL_S = 300
# Unknown slugs are cached too, so the cache must be bounded against slug-scanning.
_CACHE_MAX = 512
_QUERY = (
    '*[_type == "report" && slug.current == $slug][0]{'
    '_id, "slug": slug.current, title, "html": renderedHtml, "previewEnd": renderedPreviewEnd, '
    'excerpt, publishedAt, "updatedAt": _updatedAt, "coverUrl": cover.asset->url, '
    'bannerPinned, silo, "ctaText": cta.text, "ctaUrl": cta.url, '
    "seoTitle, seoDescription, ogTitle}"
)
# Raw perspective so open drafts are unticked too; publishing one must not re-pin it.
# Release versions are left alone: they are the editor's staged content, not live state.
_PINNED_QUERY = (
    '*[_type == "report" && bannerPinned == true'
    ' && !(_id in [$id, "drafts." + $id]) && !(_id in path("versions.**"))'
    " && ($pinnedAt == null || dateTime(_updatedAt) <= dateTime($pinnedAt))]"
    '{_id, "slug": slug.current, bannerPinned}'
)
_SOURCE_QUERY = (
    '*[_type == "report" && slug.current == $slug][0]{_id, _rev, title, bodyFormat, '
    '"body": body[]{..., _type == "image" => {"url": asset->url}}, html, renderedFrom, '
    '"freePages": coalesce(freePages, 1), "lockedPercent": coalesce(lockedPercent, 75)}'
)


class _SanityReport(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="_id")
    slug: str
    title: str
    html: str | None = None
    preview_end: int | None = Field(default=None, alias="previewEnd")
    excerpt: str | None = None
    published_at: str | None = Field(default=None, alias="publishedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    cover_url: str | None = Field(default=None, alias="coverUrl")
    banner_pinned: bool | None = Field(default=None, alias="bannerPinned")
    silo: str | None = None
    cta_text: str | None = Field(default=None, alias="ctaText")
    cta_url: str | None = Field(default=None, alias="ctaUrl")
    seo_title: str | None = Field(default=None, alias="seoTitle")
    seo_description: str | None = Field(default=None, alias="seoDescription")
    og_title: str | None = Field(default=None, alias="ogTitle")


class _QueryResponse(BaseModel):
    result: _SanityReport | None = None


class _SanitySource(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="_id")
    rev: str = Field(alias="_rev")
    # Only a rich text report prints it; pasted HTML carries its own.
    title: str = ""
    # GROQ projects an unset field as null; reports made before the toggle are all pasted HTML.
    body_format: Literal["rich", "html"] | None = Field(default=None, alias="bodyFormat")
    body: list[Block] | None = None
    html: str | None = None
    rendered_from: str | None = Field(default=None, alias="renderedFrom")
    free_pages: int = Field(default=1, ge=1, alias="freePages")
    locked_percent: int = Field(default=75, alias="lockedPercent")


class _SourceResponse(BaseModel):
    result: _SanitySource | None = None


class _Pinned(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str = Field(alias="_id")
    slug: str | None = None
    banner_pinned: bool | None = Field(default=None, alias="bannerPinned")

    def held(self, pins: list[Pin]) -> tuple[Pin, ...]:
        on: dict[Pin, bool] = {"banner": bool(self.banner_pinned)}
        return tuple(pin for pin in pins if on[pin])


class _PinnedResponse(BaseModel):
    result: list[_Pinned]


class _Unpinned(BaseModel):
    """Clears the given pins; the rest are omitted (`exclude_none`) so they are left alone."""

    model_config = ConfigDict(populate_by_name=True)

    banner_pinned: bool | None = Field(default=None, alias="bannerPinned")

    @classmethod
    def of(cls, pins: tuple[Pin, ...]) -> "_Unpinned":
        return cls(banner_pinned=False if "banner" in pins else None)


class _RenderedFields(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    rendered_html: str = Field(alias="renderedHtml")
    rendered_preview_end: int = Field(alias="renderedPreviewEnd")
    rendered_from: str = Field(alias="renderedFrom")


class _Patch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    # Sanity rejects the patch (409) if the document moved on since it was read.
    if_revision_id: str | None = Field(default=None, alias="ifRevisionID")
    set_: _RenderedFields | _Unpinned = Field(alias="set")


class _PatchMutation(BaseModel):
    patch: _Patch


class _Mutations(BaseModel):
    mutations: list[_PatchMutation]


class SanityReportSource:
    def __init__(
        self, *, project_id: str, dataset: str, write_token: str = "", timeout_s: float = 30.0
    ) -> None:
        path = f"/{API_VERSION}/data/query/{dataset}"
        self._cdn_url = f"https://{project_id}.apicdn.sanity.io{path}"
        self._api_url = f"https://{project_id}.api.sanity.io{path}"
        self._mutate_url = f"https://{project_id}.api.sanity.io/{API_VERSION}/data/mutate/{dataset}"
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
        response = await self._get(self._api_url, _SOURCE_QUERY, slug=slug)
        doc = _SourceResponse.model_validate_json(response.content).result
        if doc is None:
            return None
        if doc.body_format == "rich":
            share = (100 - doc.locked_percent) / 100
            html = rich_report(doc.title, doc.body or [], share=share)
        else:
            html = doc.html
        if not html:
            return None
        return ReportSource(
            document_id=doc.id,
            revision=doc.rev,
            html=html,
            rendered_from=doc.rendered_from,
            free_pages=doc.free_pages,
        )

    async def save_rendered(
        self, source: ReportSource, *, html: str, preview_end: int, rendered_from: str
    ) -> bool:
        fields = _RenderedFields(
            rendered_html=html, rendered_preview_end=preview_end, rendered_from=rendered_from
        )
        patch = _Patch(id=source.document_id, if_revision_id=source.revision, set_=fields)
        response = await self._mutate(_Mutations(mutations=[_PatchMutation(patch=patch)]))
        if response.status_code == 409:
            return False
        response.raise_for_status()
        return True

    async def unpin_others(
        self, pins: list[Pin], document_id: str, *, pinned_at: str | None
    ) -> list[LostPins]:
        found = await self._get(
            self._api_url, _PINNED_QUERY, raw=True, id=document_id, pinnedAt=pinned_at
        )
        losers = [
            (doc, lost)
            for doc in _PinnedResponse.model_validate_json(found.content).result
            if (lost := doc.held(pins))
        ]
        if not losers:
            return []
        patches = [
            _PatchMutation(patch=_Patch(id=doc.id, set_=_Unpinned.of(lost))) for doc, lost in losers
        ]
        (await self._mutate(_Mutations(mutations=patches))).raise_for_status()
        # A draft and its published report share a slug, hence a card: merge their pins.
        by_slug: dict[str, set[Pin]] = {}
        for doc, lost in losers:
            if doc.slug:
                by_slug.setdefault(doc.slug, set()).update(lost)
        return [
            LostPins(slug=slug, pins=tuple(p for p in pins if p in lost))
            for slug, lost in sorted(by_slug.items())
        ]

    async def _mutate(self, body: _Mutations) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            return await client.post(
                self._mutate_url,
                content=body.model_dump_json(by_alias=True, exclude_none=True),
                headers={
                    "Authorization": f"Bearer {self._write_token}",
                    "content-type": "application/json",
                },
            )

    def _store(self, slug: str, report: ReportDocument | None) -> ReportDocument | None:
        self._cache.pop(slug, None)
        if len(self._cache) >= _CACHE_MAX:
            del self._cache[next(iter(self._cache))]  # oldest write first
        self._cache[slug] = (time.monotonic() + _CACHE_TTL_S, report)
        return report

    async def _get(
        self, url: str, query: str, *, raw: bool = False, **params: str | None
    ) -> httpx.Response:
        """`raw` reads drafts too, which needs the token."""
        query_params = {"query": query} | {f"${k}": json.dumps(v) for k, v in params.items()}
        headers: dict[str, str] = {}
        if raw:
            query_params["perspective"] = "raw"
            headers["Authorization"] = f"Bearer {self._write_token}"
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(url, params=query_params, headers=headers)
        response.raise_for_status()
        return response

    async def _fetch(self, url: str, slug: str) -> ReportDocument | None:
        response = await self._get(url, _QUERY, slug=slug)
        doc = _QueryResponse.model_validate_json(response.content).result
        if doc is None or doc.html is None or doc.preview_end is None:
            return None
        return ReportDocument(
            slug=doc.slug,
            title=doc.title,
            html=doc.html,
            document_id=doc.id,
            preview_end=doc.preview_end,
            excerpt=doc.excerpt,
            published_at=doc.published_at,
            updated_at=doc.updated_at,
            cover_url=resized(doc.cover_url) if doc.cover_url else None,
            banner_pinned=bool(doc.banner_pinned),
            silo=doc.silo,
            cta_text=doc.cta_text,
            cta_url=doc.cta_url,
            seo_title=doc.seo_title,
            seo_description=doc.seo_description,
            og_title=doc.og_title,
        )
