"""The Sanity Insights-article seam. Faked in tests, implemented by
`providers/sanity/article_source.py`."""

from typing import Protocol

from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument


class ArticleSourcePort(Protocol):
    async def get(self, slug: str) -> ArticleDocument | None:
        """The published article, read fresh; `None` if unpublished or deleted."""
        ...
