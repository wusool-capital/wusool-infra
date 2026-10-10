"""Webflow implementation of `ArticlesCmsPort` — Insights articles published
from Sanity, alongside the hand-written ones in the same collection.

Every item it creates carries `sanity-managed`, and it updates or unpublishes
only those, so a hand-written article is never overwritten. The one exception
is `featured`: the `/insights` pin is shared, so a Sanity pin clears it on
hand-written items too. It never writes `hide-from-listings` or `gated`.
Option, author and silo ids are resolved by name at sync time.
"""

import logging
from dataclasses import dataclass

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument, CmsItem
from app.modules.lead_magnets.domain.insights_report.report import reading_time, word_count
from app.modules.lead_magnets.providers.webflow.collection import (
    Image,
    WebflowCollection,
)

logger = logging.getLogger(__name__)


class ArticleFieldData(BaseModel):
    """Required Webflow fields: `name`, `slug`, `content-type`, `body-content` and `excerpt`."""

    model_config = ConfigDict(populate_by_name=True)

    name: str
    slug: str
    content_type: str = Field(alias="content-type")
    excerpt: str
    body_content: str = Field(alias="body-content")
    key_takeaways: str | None = Field(default=None, alias="key-takeaways")
    faq_content: str | None = Field(default=None, alias="faq-content")
    h1_tag: str = Field(alias="h1-tag")
    # The template's <title> and meta tags bind these, so they fall back to the title and excerpt.
    seo_title: str = Field(alias="seo-title")
    seo_description: str = Field(alias="seo-description")
    og_title: str = Field(alias="og-title")
    target_keyword: str | None = Field(default=None, alias="target-keyword")
    reading_time: str = Field(alias="reading-time")
    word_count: int = Field(alias="word-count")
    published_date: str | None = Field(default=None, alias="published-date")
    last_updated: str | None = Field(default=None, alias="last-updated")
    featured_image: Image | None = Field(default=None, alias="featured-image")
    og_image: Image | None = Field(default=None, alias="og-image")
    author: str | None = None
    primary_silo: str | None = Field(default=None, alias="primary-silo")
    # Omitted when unset, like every optional field: the API documents no way to clear one.
    cta_text: str | None = Field(default=None, alias="cta-text")
    cta_url: str | None = Field(default=None, alias="cta-url")
    featured: bool
    sanity_managed: bool = Field(default=True, alias="sanity-managed")


class _FeaturedPatch(BaseModel):
    featured: bool


@dataclass(frozen=True)
class _Ids:
    """Webflow ids by name, resolved once per sync."""

    content_types: dict[str, str]
    silos: dict[str, str]
    authors: dict[str, str]


class WebflowInsightsCms:
    def __init__(self, *, token: str, collection_id: str, timeout_s: float = 15.0) -> None:
        self._collection = WebflowCollection(
            token=token, collection_id=collection_id, timeout_s=timeout_s
        )
        self._ids: _Ids | None = None

    async def find(self, slug: str) -> CmsItem | None:
        item = await self._collection.find(slug)
        if item is None:
            return None
        return CmsItem(
            id=item.id,
            managed=bool(item.field_data.sanity_managed),
            featured=bool(item.field_data.featured),
        )

    async def create(self, article: ArticleDocument) -> str:
        return await self._collection.create_live(await self.field_data(article))

    async def update(self, item_id: str, article: ArticleDocument) -> None:
        await self._collection.update_and_publish(item_id, await self.field_data(article))

    async def unpublish(self, item_id: str) -> None:
        await self._collection.unpublish(item_id)

    async def unpin_others(self, keep_id: str) -> None:
        for item in await self._collection.live_items():
            if item.field_data.featured and item.id != keep_id:
                await self._set_featured(item.id, featured=False)

    async def any_pinned(self) -> bool:
        return any(item.field_data.featured for item in await self._collection.live_items())

    async def newest_hand_written(self) -> str | None:
        listed = [
            item
            for item in await self._collection.live_items()
            if not item.field_data.sanity_managed
            and not item.field_data.hide_from_listings
            and item.field_data.published_date
        ]
        newest = max(listed, key=lambda item: item.field_data.published_date or "", default=None)
        return newest.id if newest else None

    async def pin(self, item_id: str) -> None:
        await self._set_featured(item_id, featured=True)

    async def _set_featured(self, item_id: str, *, featured: bool) -> None:
        try:
            await self._collection.patch_live(item_id, _FeaturedPatch(featured=featured))
        except httpx.HTTPStatusError as error:
            # Went off the live site since the listing; it shows no pin either way.
            if error.response.status_code not in (404, 409):
                raise
            logger.info(
                "insights_article_pin_skipped item=%s status=%s",
                item_id,
                error.response.status_code,
            )

    async def field_data(self, article: ArticleDocument) -> ArticleFieldData:
        ids = await self._load_ids()
        content_type = ids.content_types.get(article.content_type)
        if content_type is None:
            # Required by Webflow; failing here names the cause instead of a bare 400.
            raise ValueError(f"unknown Insights content type {article.content_type!r}")
        silo = ids.silos.get(article.silo or "")
        author = ids.authors.get(article.author or "")
        if article.silo and silo is None:
            logger.warning("insights_article_unknown_silo silo=%s", article.silo)
        if article.author and author is None:
            logger.warning("insights_article_unknown_author author=%s", article.author)
        cover = Image(url=article.cover_url, alt=article.title) if article.cover_url else None
        return ArticleFieldData(
            name=article.title,
            slug=article.slug,
            content_type=content_type,
            excerpt=article.excerpt,
            body_content=article.body_html,
            key_takeaways=_headed(article.key_takeaways_html, "Key Takeaways"),
            faq_content=_headed(article.faq_html, "FAQ"),
            h1_tag=article.h1 or article.title,
            seo_title=article.seo_title or article.title,
            seo_description=article.seo_description or article.excerpt,
            og_title=article.og_title or article.title,
            target_keyword=article.target_keyword,
            reading_time=reading_time(article.body_html),
            word_count=word_count(article.body_html),
            published_date=article.published_at,
            last_updated=article.updated_at,
            featured_image=cover,
            og_image=cover,
            author=author,
            primary_silo=silo,
            cta_text=article.cta_text,
            cta_url=article.cta_url,
            featured=article.featured,
        )

    async def _load_ids(self) -> _Ids:
        if self._ids is None:
            self._ids = _Ids(
                content_types=await self._collection.options("content-type"),
                silos=await self._collection.options("primary-silo"),
                authors=await self._collection.referenced_ids("author"),
            )
        return self._ids


def _headed(html: str | None, heading: str) -> str | None:
    """The template shows these fields bare; hand-written articles open each with its own h2."""
    if html is None or html.lstrip().startswith("<h2"):
        return html
    return f"<h2>{heading}</h2>{html}"
