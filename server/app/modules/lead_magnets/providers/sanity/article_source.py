"""Sanity implementation of `ArticleSourcePort`.

Read only by the publish webhook, so it always uses the uncached API host: the
CDN can still serve the old document just after a publish. Editors pick rich
text or pasted HTML per article (`bodyFormat`); either way every rich-text
field arrives here and leaves as sanitized HTML.
"""

import json
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument
from app.modules.lead_magnets.providers.sanity.portable_text import Block, sanitize, to_html
from app.modules.lead_magnets.providers.sanity.report_source import API_VERSION

logger = logging.getLogger(__name__)

_RICH = '[]{..., _type == "image" => {"url": asset->url}}'
_QUERY = (
    '*[_type == "insights" && slug.current == $slug][0]{'
    '"slug": slug.current, title, contentType, excerpt, bodyFormat, '
    f'"body": body{_RICH}, bodyHtml, "keyTakeaways": keyTakeaways{_RICH}, keyTakeawaysHtml, '
    f'"faq": faq{_RICH}, faqHtml, h1, seoTitle, seoDescription, ogTitle, targetKeyword, '
    'publishedAt, "updatedAt": _updatedAt, "coverUrl": cover.asset->url, author, silo, '
    '"ctaText": cta.text, "ctaUrl": cta.url}'
)


class _SanityArticle(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    slug: str
    title: str
    content_type: str = Field(alias="contentType")
    excerpt: str
    body_format: Literal["rich", "html"] = Field(default="rich", alias="bodyFormat")
    body: list[Block] | None = None
    body_html: str | None = Field(default=None, alias="bodyHtml")
    key_takeaways: list[Block] | None = Field(default=None, alias="keyTakeaways")
    key_takeaways_html: str | None = Field(default=None, alias="keyTakeawaysHtml")
    faq: list[Block] | None = None
    faq_html: str | None = Field(default=None, alias="faqHtml")
    h1: str | None = None
    seo_title: str | None = Field(default=None, alias="seoTitle")
    seo_description: str | None = Field(default=None, alias="seoDescription")
    og_title: str | None = Field(default=None, alias="ogTitle")
    target_keyword: str | None = Field(default=None, alias="targetKeyword")
    published_at: str | None = Field(default=None, alias="publishedAt")
    updated_at: str | None = Field(default=None, alias="updatedAt")
    cover_url: str | None = Field(default=None, alias="coverUrl")
    author: str | None = None
    silo: str | None = None
    cta_text: str | None = Field(default=None, alias="ctaText")
    cta_url: str | None = Field(default=None, alias="ctaUrl")

    def html(self, blocks: list[Block] | None, pasted: str | None) -> str | None:
        """The field in the editor's chosen format; the other one is ignored even if filled."""
        if self.body_format == "html":
            html = sanitize(pasted) if pasted else ""
        else:
            html = to_html(blocks) if blocks else ""
        # Judged after cleaning: a paste that was only a script or a table is empty.
        return html if html.strip() else None


class _QueryResponse(BaseModel):
    result: _SanityArticle | None = None


class SanityArticleSource:
    def __init__(self, *, project_id: str, dataset: str, timeout_s: float = 30.0) -> None:
        self._url = f"https://{project_id}.api.sanity.io/{API_VERSION}/data/query/{dataset}"
        self._timeout_s = timeout_s

    async def get(self, slug: str) -> ArticleDocument | None:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(
                self._url, params={"query": _QUERY, "$slug": json.dumps(slug)}
            )
        response.raise_for_status()
        doc = _QueryResponse.model_validate_json(response.content).result
        if doc is None:
            return None
        body = doc.html(doc.body, doc.body_html)
        if body is None:
            # The Studio requires a body; treated as unpublished rather than written blank.
            logger.warning("insights_article_no_body slug=%s", slug)
            return None
        return ArticleDocument(
            slug=doc.slug,
            title=doc.title,
            content_type=doc.content_type,
            excerpt=doc.excerpt,
            body_html=body,
            key_takeaways_html=doc.html(doc.key_takeaways, doc.key_takeaways_html),
            faq_html=doc.html(doc.faq, doc.faq_html),
            h1=doc.h1,
            seo_title=doc.seo_title,
            seo_description=doc.seo_description,
            og_title=doc.og_title,
            target_keyword=doc.target_keyword,
            published_at=doc.published_at,
            updated_at=doc.updated_at,
            cover_url=doc.cover_url,
            author=doc.author,
            silo=doc.silo,
            cta_text=doc.cta_text,
            cta_url=doc.cta_url,
        )
