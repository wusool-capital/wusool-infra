"""Keeps a Webflow Insights article in step with one published in Sanity.

Triggered by the same Sanity webhook as reports. Every call re-reads the
article rather than trusting the webhook body, so a retried or out-of-order
delivery still lands the current state. Hand-written Webflow articles share
the collection, so only items this sync created are ever written, except for
the one `/insights` pin, which a Sanity article takes from any item.

When a sync releases the pin and nothing else holds it, the newest Sanity
article takes it; with none, the newest hand-written one does.
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
        released = False
        if previous_slug and previous_slug != slug:
            released = await self._unpublish(previous_slug)
        article = await self._source.get(slug) if slug else None
        if slug and article is None:
            released = await self._unpublish(slug) or released
        elif article is not None:
            released = await self._write(article) or released
        if released:
            await self._fill_pin(excluding=article.document_id if article else None)

    async def _write(self, article: ArticleDocument) -> bool:
        """Whether this write released the pin."""
        item = await self._cms.find(article.slug)
        if item is not None and not item.managed:
            logger.warning("insights_article_sync_skipped_unmanaged slug=%s", article.slug)
            return False
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
        return item is not None and item.featured and not article.featured

    async def _unpublish(self, slug: str) -> bool:
        """Whether this unpublish released the pin."""
        item = await self._cms.find(slug)
        if item is None or not item.managed:
            return False
        await self._cms.unpublish(item.id)
        return item.featured

    async def _fill_pin(self, *, excluding: str | None) -> None:
        # Judged on final state, so a rename or a newer pin elsewhere is left alone.
        # ponytail: two releases at once can pin two articles; add a lock if that ever bites.
        if await self._source.any_pinned() or await self._cms.any_pinned():
            return
        # Its own webhook then pins the Webflow item.
        if await self._source.pin_newest(excluding=excluding):
            return
        if item_id := await self._cms.newest_hand_written():
            await self._cms.pin(item_id)
