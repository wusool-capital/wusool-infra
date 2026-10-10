"""The Webflow Insights collection seam for Sanity articles. Faked in tests,
implemented by `providers/webflow/insights_cms.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument, CmsItem


class ArticlesCmsPort(Protocol):
    async def find(self, slug: str) -> CmsItem | None: ...

    async def create(self, article: ArticleDocument) -> str:
        """Creates the item already published to the live site and returns its id."""
        ...

    async def update(self, item_id: str, article: ArticleDocument) -> None: ...

    async def unpublish(self, item_id: str) -> None: ...

    async def unpin_others(self, keep_id: str) -> None:
        """Clears `featured` on every other live item, hand-written ones included."""
        ...

    async def any_pinned(self) -> bool:
        """Whether a live item is featured."""
        ...

    async def newest_hand_written(self) -> str | None:
        """The id of the newest live, listed article the sync did not create."""
        ...

    async def pin(self, item_id: str) -> None:
        """Sets `featured` on the live item only."""
        ...
