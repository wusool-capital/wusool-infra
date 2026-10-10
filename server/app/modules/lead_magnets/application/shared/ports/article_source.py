"""The Sanity Insights-article seam. Faked in tests, implemented by
`providers/sanity/article_source.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument


class ArticleSourcePort(Protocol):
    async def get(self, slug: str) -> ArticleDocument | None:
        """The published article, read fresh; `None` if unpublished or deleted."""
        ...

    async def unpin_others(self, document_id: str, *, pinned_at: str | None) -> None:
        """Unticks the pin on every other article, drafts included, last edited no
        later than `pinned_at`, in one transaction, so the later of two pins wins."""
        ...

    async def any_pinned(self) -> bool:
        """Whether a published article holds the pin."""
        ...

    async def pin_newest(self, *, excluding: str | None) -> bool:
        """Ticks the pin on the newest published article other than `excluding`,
        and on its open draft. `False` when there is none."""
        ...
