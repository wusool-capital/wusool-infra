"""Keeps a Webflow Insights article in step with one published in Sanity.

Triggered by the same Sanity webhook as reports. Every call re-reads the
article rather than trusting the webhook body, so a retried or out-of-order
delivery still lands the current state. Hand-written Webflow articles share
the collection, so only items this sync created are ever written.
"""

import logging

from app.modules.lead_magnets.application.shared.ports import (
    ArticlesCmsPort,
    ArticleSourcePort,
)

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

        item = await self._cms.find(slug)
        if item is None:
            await self._cms.create(article)
        elif item.managed:
            await self._cms.update(item.id, article)
        else:
            logger.warning("insights_article_sync_skipped_unmanaged slug=%s", slug)

    async def _unpublish(self, slug: str) -> None:
        item = await self._cms.find(slug)
        if item is not None and item.managed:
            await self._cms.unpublish(item.id)
