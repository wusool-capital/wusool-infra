"""An Insights article published from Sanity, as the rest of the module sees it.

`providers/sanity` builds one, with every rich-text field already HTML, and
`providers/webflow` writes it to the Insights collection. Pure — no vendor types.
"""

from dataclasses import dataclass
from html import escape


@dataclass(frozen=True)
class ArticleDocument:
    slug: str
    title: str
    # A Webflow "Content Type" option name, such as "Article".
    content_type: str
    excerpt: str
    body_html: str
    # The published Sanity document id; pins are matched by id, since a draft can rename the slug.
    document_id: str
    featured: bool = False
    key_takeaways_html: str | None = None
    faq_html: str | None = None
    h1: str | None = None
    seo_title: str | None = None
    seo_description: str | None = None
    og_title: str | None = None
    target_keyword: str | None = None
    published_at: str | None = None
    updated_at: str | None = None
    cover_url: str | None = None
    author: str | None = None
    silo: str | None = None
    cta_text: str | None = None
    cta_url: str | None = None
    # Set when the HTML file is the whole page; `body_html` then marks where it mounts.
    page_url: str | None = None


def text_paragraphs(text: str) -> str:
    """Plain text as escaped paragraphs, one per non-blank line."""
    return "".join(f"<p>{escape(line.strip())}</p>" for line in text.splitlines() if line.strip())


@dataclass(frozen=True)
class PendingExhibits:
    """Charts whose still image hasn't been captured from the article's current HTML file."""

    document_id: str
    revision: str
    bundle_url: str
    ids: tuple[str, ...]
    # Every chart's still so far, kept when the new ones are saved.
    stills: dict[str, str]


@dataclass(frozen=True)
class CmsItem:
    """An existing Insights item, reduced to what the sync decides on."""

    id: str
    # Only items the sync created; hand-written articles are never overwritten.
    managed: bool
