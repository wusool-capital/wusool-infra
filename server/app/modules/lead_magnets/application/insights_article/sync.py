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

from app.modules.lead_magnets.application.shared.ports import (
    ArticlesCmsPort,
    ArticleSourcePort,
)
from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument

logger = logging.getLogger(__name__)


class ArticleSync:
    def __init__(self, *, source: ArticleSourcePort, cms: ArticlesCmsPort) -> None:
        self._source = source
        self._cms = cms

    async def sync(self, *, slug: str | None, previous_slug: str | None) -> None:
        """`slug` is `None` when the article was deleted or unpublished;
        `previous_slug` differs from it when an editor renamed the slug."""
        if previous_slug and previous_slug != slug:
            await self._unpublish(previous_slug)
        if slug is None:
            return

        article = await self._source.get(slug)
        if article is None:
            await self._unpublish(slug)
            return
        await self._write(article)

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
            # After this item is live, so a failed write never empties the pin. Sanity
            # is unticked last: each loser's own webhook then repairs a failed Webflow unpin.
            await self._cms.unpin_others(item_id)
            await self._source.unpin_others(article.document_id, pinned_at=article.updated_at)

    async def _unpublish(self, slug: str) -> None:
        item = await self._cms.find(slug)
        if item is not None and item.managed:
            await self._cms.unpublish(item.id)
