"""Webflow implementation of `InsightsCmsPort` — the `/insights` listing card.

Field slugs are the live Insights collection's own (read through the
Webflow API, 2026-10-05). Option and Team ids are resolved by name at sync
time, never hardcoded, so renaming an author in Webflow doesn't break this.

Every write uses the `/live` endpoints, so the card should reach the live site
without a Designer publish. Not yet verified with a real token.
"""

import logging
from html import escape

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report import (
    CmsItem,
    ReportDocument,
    reading_time,
)

logger = logging.getLogger(__name__)

_API = "https://api.webflow.com/v2"
_PAGE = 100
_REPORT_CONTENT_TYPE = "Report"
# Webflow fetches the image itself and rejects anything over 4MB.
_COVER_PARAMS = "?w=1600&fm=jpg"


class _Option(BaseModel):
    id: str
    name: str


class _Validations(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    options: list[_Option] = []
    collection_id: str | None = Field(default=None, alias="collectionId")


class _CollectionField(BaseModel):
    slug: str
    validations: _Validations | None = None


class _Collection(BaseModel):
    fields: list[_CollectionField]


class _ItemFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    slug: str | None = None
    gated: bool | None = None
    featured: bool | None = None


class _Item(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    field_data: _ItemFields = Field(alias="fieldData")


class _Pagination(BaseModel):
    total: int


class _ItemList(BaseModel):
    items: list[_Item]
    pagination: _Pagination


class _Image(BaseModel):
    url: str
    alt: str


class InsightFieldData(BaseModel):
    """The card written for a gated report. Required Webflow fields:
    `name`, `slug`, `content-type`, `body-content` and `excerpt`."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    slug: str
    content_type: str = Field(alias="content-type")
    gated: bool = True
    featured: bool | None = None
    excerpt: str
    # Required by Webflow; the template hides it on gated items, where the report replaces it.
    body_content: str = Field(alias="body-content")
    # The template's <title> and meta tags bind these, so they must never be blank.
    seo_title: str = Field(alias="seo-title")
    seo_description: str = Field(alias="seo-description")
    og_title: str = Field(alias="og-title")
    reading_time: str = Field(alias="reading-time")
    published_date: str | None = Field(default=None, alias="published-date")
    last_updated: str | None = Field(default=None, alias="last-updated")
    featured_image: _Image | None = Field(default=None, alias="featured-image")
    og_image: _Image | None = Field(default=None, alias="og-image")
    author: str | None = None
    primary_silo: str | None = Field(default=None, alias="primary-silo")


class _FeaturedPatch(BaseModel):
    featured: bool


class _ItemWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Omitted on the unpin write: it must not change a hand-written article's draft state.
    is_draft: bool | None = Field(default=None, alias="isDraft")
    field_data: InsightFieldData | _FeaturedPatch = Field(alias="fieldData")


class _Schema(BaseModel):
    report_option_id: str
    silo_ids: dict[str, str]
    author_ids: dict[str, str]


class WebflowInsightsCms:
    def __init__(self, *, token: str, collection_id: str, timeout_s: float = 15.0) -> None:
        self._headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
        self._collection_id = collection_id
        self._timeout_s = timeout_s
        self._schema: _Schema | None = None

    async def find(self, slug: str) -> CmsItem | None:
        # Staged items, so an unpublished card is reused rather than clashing on slug.
        page = await self._list(f"/collections/{self._collection_id}/items", slug=slug)
        # Checked here, not trusted: a loose filter must never hand back another card to overwrite.
        item = next((i for i in page.items if i.field_data.slug == slug), None)
        if item is None:
            return None
        return CmsItem(id=item.id, gated=bool(item.field_data.gated))

    async def create(self, report: ReportDocument, *, featured: bool | None) -> None:
        body = _ItemWrite(is_draft=False, field_data=await self.field_data(report, featured))
        await self._request("POST", f"/collections/{self._collection_id}/items/live", body=body)

    async def update(self, item_id: str, report: ReportDocument, *, featured: bool | None) -> None:
        body = _ItemWrite(is_draft=False, field_data=await self.field_data(report, featured))
        await self._request(
            "PATCH", f"/collections/{self._collection_id}/items/{item_id}/live", body=body
        )

    async def unpublish(self, item_id: str) -> None:
        await self._request("DELETE", f"/collections/{self._collection_id}/items/{item_id}/live")

    async def featured_ids(self) -> list[str]:
        ids: list[str] = []
        offset = 0
        while True:
            page = await self._list(f"/collections/{self._collection_id}/items/live", offset=offset)
            ids += [item.id for item in page.items if item.field_data.featured]
            offset += _PAGE
            if offset >= page.pagination.total:
                return ids

    async def unfeature(self, item_id: str) -> None:
        await self._request(
            "PATCH",
            f"/collections/{self._collection_id}/items/{item_id}/live",
            body=_ItemWrite(field_data=_FeaturedPatch(featured=False)),
        )

    async def field_data(
        self, report: ReportDocument, featured: bool | None = None
    ) -> InsightFieldData:
        """`featured` `None` leaves the card's pin untouched (omitted from the write)."""
        schema = await self._load_schema()
        cover = (
            _Image(url=report.cover_url + _COVER_PARAMS, alt=report.title)
            if report.cover_url
            else None
        )
        author = schema.author_ids.get(report.author or "")
        silo = schema.silo_ids.get(report.silo or "")
        if report.author and author is None:
            logger.warning("insights_report_unknown_author author=%s", report.author)
        if report.silo and silo is None:
            logger.warning("insights_report_unknown_silo silo=%s", report.silo)
        return InsightFieldData(
            name=report.title,
            slug=report.slug,
            content_type=schema.report_option_id,
            featured=featured,
            excerpt=report.excerpt,
            body_content=f"<p>{escape(report.excerpt)}</p>",
            seo_title=report.title,
            seo_description=report.excerpt,
            og_title=report.title,
            reading_time=reading_time(report.html),
            published_date=report.published_at,
            last_updated=report.updated_at,
            featured_image=cover,
            og_image=cover,
            author=author,
            primary_silo=silo,
        )

    async def _load_schema(self) -> _Schema:
        if self._schema is not None:
            return self._schema
        response = await self._request("GET", f"/collections/{self._collection_id}")
        fields = {
            f.slug: f.validations or _Validations()
            for f in _Collection.model_validate_json(response.content).fields
        }
        content_types = {o.name: o.id for o in fields["content-type"].options}
        silo_ids = {o.name: o.id for o in fields["primary-silo"].options}
        author_ids: dict[str, str] = {}
        if team_collection := fields["author"].collection_id:
            team = await self._list(f"/collections/{team_collection}/items")
            author_ids = {i.field_data.name: i.id for i in team.items if i.field_data.name}
        self._schema = _Schema(
            report_option_id=content_types[_REPORT_CONTENT_TYPE],
            silo_ids=silo_ids,
            author_ids=author_ids,
        )
        return self._schema

    async def _list(self, path: str, *, offset: int = 0, slug: str | None = None) -> _ItemList:
        params: dict[str, str | int] = {"limit": _PAGE, "offset": offset}
        if slug is not None:
            params["slug"] = slug
        response = await self._request("GET", path, params=params)
        return _ItemList.model_validate_json(response.content)

    async def _request(
        self,
        method: str,
        path: str,
        *,
        params: dict[str, str | int] | None = None,
        body: _ItemWrite | None = None,
    ) -> httpx.Response:
        content = body.model_dump_json(by_alias=True, exclude_none=True) if body else None
        headers = {**self._headers, "content-type": "application/json"} if body else self._headers
        async with httpx.AsyncClient(timeout=self._timeout_s, headers=headers) as client:
            response = await client.request(method, _API + path, params=params, content=content)
        response.raise_for_status()
        return response
