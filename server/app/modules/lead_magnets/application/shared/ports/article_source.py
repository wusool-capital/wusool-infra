"""The Sanity Insights-article seam. Faked in tests, implemented by
`providers/sanity/article_source.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_article.article import (
    ArticleDocument,
    PendingExhibits,
)


class ArticleSourcePort(Protocol):
    async def get(self, slug: str) -> ArticleDocument | None:
        """The published article, read fresh; `None` if unpublished or deleted."""
        ...

    async def pending_exhibits(self, slug: str) -> PendingExhibits | None:
        """The charts in the body with no still image for the article's current HTML
        file, or `None` when there is nothing to capture."""
        ...

    async def bundle(self, pending: PendingExhibits) -> str:
        """The article's HTML file. Raises on a failed download."""
        ...

    async def upload_image(self, data: bytes, mime: str) -> str:
        """Stores one image and returns its CDN URL. Raises on failure."""
        ...

    async def save_exhibit_images(self, pending: PendingExhibits, urls: dict[str, str]) -> bool:
        """Keeps the chart stills on the article. `False` when it changed since
        `pending` was read; nothing is saved."""
        ...

    async def unpin_others(self, document_id: str, *, pinned_at: str | None) -> None:
        """Unticks the pin on every other article, drafts included, last edited no
        later than `pinned_at`, in one transaction, so the later of two pins wins."""
        ...
