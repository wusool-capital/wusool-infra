"""Webflow implementation of `ReportsCmsPort` — the `/reports` listing card.

Field slugs are the live Reports collection's own (created 2026-10-07).
Silo option ids are resolved by name at sync time, never hardcoded.

Cards reach the live site without a Designer publish. A card update is written
to the staged item and then published, because the `/live` update 409s
("Item not published") on a card an earlier sync unpublished.
"""

import logging

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report import (
    ReportDocument,
    reading_time,
)

logger = logging.getLogger(__name__)

_API = "https://api.webflow.com/v2"
_PAGE = 100
# Webflow fetches the image itself and rejects anything over 4MB.
_COVER_PARAMS = "?w=1600&fm=jpg"


class _Option(BaseModel):
    id: str
    name: str


class _Validations(BaseModel):
    options: list[_Option] = []


class _CollectionField(BaseModel):
    slug: str
    validations: _Validations | None = None


class _Collection(BaseModel):
    fields: list[_CollectionField]


class _ItemFields(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    slug: str | None = None
    featured: bool | None = None
    published_date: str | None = Field(default=None, alias="published-date")


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


class ReportFieldData(BaseModel):
    """The card written for a gated report. Required Webflow fields:
    `name`, `slug` and `excerpt`."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    slug: str
    featured: bool | None = None
    excerpt: str
    # The template's <title> and meta tags bind these, so they must never be blank.
    seo_title: str = Field(alias="seo-title")
    seo_description: str = Field(alias="seo-description")
    og_title: str = Field(alias="og-title")
    reading_time: str = Field(alias="reading-time")
    published_date: str | None = Field(default=None, alias="published-date")
    last_updated: str | None = Field(default=None, alias="last-updated")
    featured_image: _Image | None = Field(default=None, alias="featured-image")
    og_image: _Image | None = Field(default=None, alias="og-image")
    primary_silo: str | None = Field(default=None, alias="primary-silo")
    # Omitted when unset, like every optional field: the API documents no way to clear one.
    cta_text: str | None = Field(default=None, alias="cta-text")
    cta_url: str | None = Field(default=None, alias="cta-url")


class _FeaturedPatch(BaseModel):
    featured: bool


class _Publish(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    item_ids: list[str] = Field(alias="itemIds")


class _Published(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    published_item_ids: list[str] = Field(default=[], alias="publishedItemIds")


class _Created(BaseModel):
    id: str


class _ItemWrite(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    # Omitted on pin writes: a pin must not change a card's draft state.
    is_draft: bool | None = Field(default=None, alias="isDraft")
    field_data: ReportFieldData | _FeaturedPatch = Field(alias="fieldData")


class WebflowReportsCms:
    def __init__(self, *, token: str, collection_id: str, timeout_s: float = 15.0) -> None:
        self._headers = {"Authorization": f"Bearer {token}", "accept": "application/json"}
        self._collection_id = collection_id
        self._timeout_s = timeout_s
        self._silo_ids: dict[str, str] | None = None

    async def find(self, slug: str) -> str | None:
        # Staged items, so an unpublished card is reused rather than clashing on slug.
        page = await self._list(f"/collections/{self._collection_id}/items", slug=slug)
        # Checked here, not trusted: a loose filter must never hand back another card to overwrite.
        return next((i.id for i in page.items if i.field_data.slug == slug), None)

    async def create(self, report: ReportDocument, *, featured: bool | None) -> str:
        body = _ItemWrite(is_draft=False, field_data=await self.field_data(report, featured))
        response = await self._request(
            "POST", f"/collections/{self._collection_id}/items/live", body=body
        )
        return _Created.model_validate_json(response.content).id

    async def update(self, item_id: str, report: ReportDocument, *, featured: bool | None) -> None:
        body = _ItemWrite(is_draft=False, field_data=await self.field_data(report, featured))
        await self._request(
            "PATCH", f"/collections/{self._collection_id}/items/{item_id}", body=body
        )
        response = await self._request(
            "POST",
            f"/collections/{self._collection_id}/items/publish",
            body=_Publish(item_ids=[item_id]),
        )
        # Per-item failures come back in a 202, not as an HTTP error.
        if item_id not in _Published.model_validate_json(response.content).published_item_ids:
            raise RuntimeError(f"Webflow did not publish item {item_id}")

    async def unpublish(self, item_id: str) -> None:
        try:
            await self._request(
                "DELETE", f"/collections/{self._collection_id}/items/{item_id}/live"
            )
        except httpx.HTTPStatusError as error:
            # Already off the live site, e.g. an earlier sync unpublished it.
            if error.response.status_code != 404:
                raise

    async def featured_ids(self) -> list[str]:
        return [item.id for item in await self._live_items() if item.field_data.featured]

    async def newest_id(self, *, excluding: str | None = None) -> str | None:
        dated = [
            item
            for item in await self._live_items()
            if item.field_data.published_date and item.id != excluding
        ]
        if not dated:
            return None
        return max(dated, key=lambda item: item.field_data.published_date or "").id

    async def feature(self, item_id: str) -> None:
        await self._pin(item_id, featured=True)

    async def unfeature(self, item_id: str) -> None:
        await self._pin(item_id, featured=False)

    async def _pin(self, item_id: str, *, featured: bool) -> None:
        await self._request(
            "PATCH",
            f"/collections/{self._collection_id}/items/{item_id}/live",
            body=_ItemWrite(field_data=_FeaturedPatch(featured=featured)),
        )

    async def _live_items(self) -> list[_Item]:
        items: list[_Item] = []
        offset = 0
        while True:
            page = await self._list(f"/collections/{self._collection_id}/items/live", offset=offset)
            items += page.items
            offset += _PAGE
            if offset >= page.pagination.total:
                return items

    async def field_data(
        self, report: ReportDocument, featured: bool | None = None
    ) -> ReportFieldData:
        """`featured` `None` leaves the card's pin untouched (omitted from the write)."""
        silo_ids = await self._load_silo_ids()
        cover = (
            _Image(url=report.cover_url + _COVER_PARAMS, alt=report.title)
            if report.cover_url
            else None
        )
        silo = silo_ids.get(report.silo or "")
        if report.silo and silo is None:
            logger.warning("insights_report_unknown_silo silo=%s", report.silo)
        return ReportFieldData(
            name=report.title,
            slug=report.slug,
            featured=featured,
            excerpt=report.excerpt,
            seo_title=report.title,
            seo_description=report.excerpt,
            og_title=report.title,
            reading_time=reading_time(report.html),
            published_date=report.published_at,
            last_updated=report.updated_at,
            featured_image=cover,
            og_image=cover,
            primary_silo=silo,
            cta_text=report.cta_text,
            cta_url=report.cta_url,
        )

    async def _load_silo_ids(self) -> dict[str, str]:
        if self._silo_ids is not None:
            return self._silo_ids
        response = await self._request("GET", f"/collections/{self._collection_id}")
        fields = {
            f.slug: f.validations or _Validations()
            for f in _Collection.model_validate_json(response.content).fields
        }
        self._silo_ids = {o.name: o.id for o in fields["primary-silo"].options}
        return self._silo_ids

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
        body: _ItemWrite | _Publish | None = None,
    ) -> httpx.Response:
        content = body.model_dump_json(by_alias=True, exclude_none=True) if body else None
        headers = {**self._headers, "content-type": "application/json"} if body else self._headers
        async with httpx.AsyncClient(timeout=self._timeout_s, headers=headers) as client:
            response = await client.request(method, _API + path, params=params, content=content)
        response.raise_for_status()
        return response
