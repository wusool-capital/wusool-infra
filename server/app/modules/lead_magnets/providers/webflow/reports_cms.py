"""Webflow implementation of `ReportsCmsPort` — the `/reports` listing card.

Field slugs are the live Reports collection's own (created 2026-10-07).
Silo option ids are resolved by name at sync time, never hardcoded.
"""

import logging

from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_report.report import (
    ReportDocument,
    reading_time,
)
from app.modules.lead_magnets.providers.webflow.collection import (
    Image,
    WebflowCollection,
)

logger = logging.getLogger(__name__)


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
    featured_image: Image | None = Field(default=None, alias="featured-image")
    og_image: Image | None = Field(default=None, alias="og-image")
    primary_silo: str | None = Field(default=None, alias="primary-silo")
    # Omitted when unset, like every optional field: the API documents no way to clear one.
    cta_text: str | None = Field(default=None, alias="cta-text")
    cta_url: str | None = Field(default=None, alias="cta-url")


class _FeaturedPatch(BaseModel):
    featured: bool


class WebflowReportsCms:
    def __init__(self, *, token: str, collection_id: str, timeout_s: float = 15.0) -> None:
        self._collection = WebflowCollection(
            token=token, collection_id=collection_id, timeout_s=timeout_s
        )
        self._silo_ids: dict[str, str] | None = None

    async def find(self, slug: str) -> str | None:
        item = await self._collection.find(slug)
        return item.id if item else None

    async def create(self, report: ReportDocument, *, featured: bool | None) -> str:
        return await self._collection.create_live(await self.field_data(report, featured))

    async def update(self, item_id: str, report: ReportDocument, *, featured: bool | None) -> None:
        await self._collection.update_and_publish(item_id, await self.field_data(report, featured))

    async def unpublish(self, item_id: str) -> None:
        await self._collection.unpublish(item_id)

    async def featured_ids(self) -> list[str]:
        return [i.id for i in await self._collection.live_items() if i.field_data.featured]

    async def newest_id(self, *, excluding: str | None = None) -> str | None:
        dated = [
            item
            for item in await self._collection.live_items()
            if item.field_data.published_date and item.id != excluding
        ]
        if not dated:
            return None
        return max(dated, key=lambda item: item.field_data.published_date or "").id

    async def feature(self, item_id: str) -> None:
        await self._collection.patch_live(item_id, _FeaturedPatch(featured=True))

    async def unfeature(self, item_id: str) -> None:
        await self._collection.patch_live(item_id, _FeaturedPatch(featured=False))

    async def field_data(
        self, report: ReportDocument, featured: bool | None = None
    ) -> ReportFieldData:
        """`featured` `None` leaves the card's pin untouched (omitted from the write)."""
        if self._silo_ids is None:
            self._silo_ids = await self._collection.options("primary-silo")
        cover = Image(url=report.cover_url, alt=report.title) if report.cover_url else None
        silo = self._silo_ids.get(report.silo or "")
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
