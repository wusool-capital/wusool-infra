"""Keeps a Webflow Insights article in step with one published in Sanity.

Triggered by the same Sanity webhook as reports. Every call re-reads the
article rather than trusting the webhook body, so a retried or out-of-order
delivery still lands the current state. Hand-written Webflow articles share
the collection, so only items this sync created are ever written, except for
the one `/insights` pin, which a Sanity article takes from any item.

With no pin, the `/insights` featured block shows the newest article by its
own sort, as on `/reports`; the sync never refills it.
"""

import logging
from dataclasses import replace

from app.modules.lead_magnets.application.shared.ports import (
    ArticlesCmsPort,
    ArticleSourcePort,
    ReportRendererPort,
)
from app.modules.lead_magnets.domain.insights_article.article import (
    ArticleDocument,
    text_paragraphs,
)

logger = logging.getLogger(__name__)


class ArticleSync:
    def __init__(
        self, *, source: ArticleSourcePort, cms: ArticlesCmsPort, renderer: ReportRendererPort
    ) -> None:
        self._source = source
        self._cms = cms
        self._renderer = renderer

    async def sync(self, *, slug: str | None, previous_slug: str | None) -> None:
        """`slug` is `None` when the article was deleted or unpublished;
        `previous_slug` differs from it when an editor renamed the slug."""
        if previous_slug and previous_slug != slug:
            await self._unpublish(previous_slug)
        if slug is None:
            return

        if not await self._capture_stills(slug):
            # Edited again mid-capture; that edit's own webhook syncs the newer version.
            logger.info("insights_article_sync_superseded slug=%s", slug)
            return

        article = await self._source.get(slug)
        if article is None:
            await self._unpublish(slug)
            return
        if article.page_url:
            article = await self._with_page_text(article, article.page_url)
        await self._write(article)

    async def _with_page_text(self, article: ArticleDocument, url: str) -> ArticleDocument:
        """The page's text below its marker, for search engines; the live page covers it."""
        try:
            text = await self._renderer.text(await self._source.html_file(url))
        except Exception:
            # The marker alone still shows the page; only the indexable copy is missing.
            logger.exception("insights_article_page_text_failed slug=%s", article.slug)
            return article
        return replace(article, body_html=article.body_html + text_paragraphs(text))

    async def _capture_stills(self, slug: str) -> bool:
        """False only when the article changed mid-capture. A failure leaves the charts out."""
        try:
            pending = await self._source.pending_exhibits(slug)
            if pending is None:
                return True
            shots = await self._renderer.exhibit_images(
                await self._source.html_file(pending.bundle_url), pending.ids
            )
            urls = {
                exhibit_id: await self._source.upload_image(png, "image/png")
                for exhibit_id, png in shots.items()
            }
            return await self._source.save_exhibit_images(pending, urls)
        except Exception:
            # A wrong chart id or a Chromium timeout must not block unrelated text edits.
            logger.exception("insights_article_stills_failed slug=%s", slug)
            return True

    async def _write(self, article: ArticleDocument) -> None:
        item = await self._cms.find(article.slug)
        if item is not None and not item.managed:
            logger.warning("insights_article_sync_skipped_unmanaged slug=%s", article.slug)
            return
        if item is None:
            item_id = await self._cms.create(article)
        else:
            item_id = item.id
            await self._cms.update(item_id, article)
        if article.featured:
            # Sanity first: each unticked article's own webhook then rewrites its Webflow item.
            await self._source.unpin_others(article.document_id, pinned_at=article.updated_at)
            await self._cms.unpin_others(item_id)

    async def _unpublish(self, slug: str) -> None:
        item = await self._cms.find(slug)
        if item is not None and item.managed:
            await self._cms.unpublish(item.id)
