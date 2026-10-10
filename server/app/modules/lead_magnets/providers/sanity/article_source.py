"""Sanity implementation of `ArticleSourcePort`.

Read only by the publish webhook, so it always uses the uncached API host: the
CDN can still serve the old document just after a publish. Editors pick rich
text or pasted HTML per article (`bodyFormat`); either way every rich-text
field arrives here and leaves as sanitized HTML.

Its only writes move the `/insights` pin, with the write token. Each one fires
the webhook for the article it changed, whose own sync then updates Webflow.
"""

import json
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument
from app.modules.lead_magnets.providers.sanity.images import resized
from app.modules.lead_magnets.providers.sanity.portable_text import Block, sanitize, to_html
from app.modules.lead_magnets.providers.sanity.report_source import API_VERSION

logger = logging.getLogger(__name__)

_RICH = '[]{..., _type == "image" => {"url": asset->url}}'
_QUERY = (
    '*[_type == "insights" && slug.current == $slug][0]{'
    '_id, featured, "slug": slug.current, title, contentType, excerpt, bodyFormat, '
    f'"body": body{_RICH}, bodyHtml, "keyTakeaways": keyTakeaways{_RICH}, keyTakeawaysHtml, '
    f'"faq": faq{_RICH}, faqHtml, h1, seoTitle, seoDescription, ogTitle, targetKeyword, '
    'publishedAt, "updatedAt": _updatedAt, "coverUrl": cover.asset->url, author, silo, '
    '"ctaText": cta.text, "ctaUrl": cta.url}'
)
# Raw perspective, so open drafts are unticked too; publishing one must not re-pin it.
_PINNED_QUERY = (
    '*[_type == "insights" && featured == true'
    ' && !(_id in [$id, "drafts." + $id]) && !(_id in path("versions.**"))'
    " && ($pinnedAt == null || dateTime(_updatedAt) <= dateTime($pinnedAt))]._id"
)
_ANY_PINNED_QUERY = 'count(*[_type == "insights" && featured == true]) > 0'
# Raw perspective again, filtered back to published documents; returns the newest and its draft.
_NEWEST_QUERY = (
    '*[_type == "insights" && !(_id in path("drafts.**")) && !(_id in path("versions.**"))'
    " && _id != $id] | order(coalesce(publishedAt, _createdAt) desc)[0]"
    '{"ids": *[_id in [^._id, "drafts." + ^._id]]._id}'
)


class _SanityArticle(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="_id")
    featured: bool | None = None
    slug: str
    title: str
    content_type: str = Field(alias="contentType")
    excerpt: str
    # GROQ projects an unset field as null, read as pasted HTML like the Studio does.
    body_format: Literal["rich", "html"] | None = Field(default=None, alias="bodyFormat")
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
        if self.body_format != "rich":
            html = sanitize(pasted) if pasted else ""
        else:
            html = to_html(blocks) if blocks else ""
        # Judged after cleaning: a paste that was only a script or a table is empty.
        return html if html.strip() else None


class _QueryResponse(BaseModel):
    result: _SanityArticle | None = None


class _IdsResponse(BaseModel):
    result: list[str]


class _AnyPinnedResponse(BaseModel):
    result: bool


class _Newest(BaseModel):
    ids: list[str]


class _NewestResponse(BaseModel):
    result: _Newest | None = None


class _Featured(BaseModel):
    featured: bool


class _Patch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    set_: _Featured = Field(alias="set")


class _PatchMutation(BaseModel):
    patch: _Patch


class _Mutations(BaseModel):
    mutations: list[_PatchMutation]

    @classmethod
    def featured(cls, ids: list[str], *, featured: bool) -> "_Mutations":
        return cls(
            mutations=[
                _PatchMutation(patch=_Patch(id=i, set_=_Featured(featured=featured))) for i in ids
            ]
        )


class SanityArticleSource:
    def __init__(
        self, *, project_id: str, dataset: str, write_token: str = "", timeout_s: float = 30.0
    ) -> None:
        host = f"https://{project_id}.api.sanity.io/{API_VERSION}/data"
        self._url = f"{host}/query/{dataset}"
        self._mutate_url = f"{host}/mutate/{dataset}"
        self._write_token = write_token
        self._timeout_s = timeout_s

    async def get(self, slug: str) -> ArticleDocument | None:
        response = await self._query(_QUERY, slug=slug)
        doc = _QueryResponse.model_validate_json(response.content).result
        if doc is None:
            return None
        body = doc.html(doc.body, doc.body_html)
        if body is None:
            # The Studio requires a body; treated as unpublished rather than written blank.
            logger.warning("insights_article_no_body slug=%s", slug)
            return None
        return ArticleDocument(
            document_id=doc.id,
            featured=bool(doc.featured),
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
            cover_url=resized(doc.cover_url) if doc.cover_url else None,
            author=doc.author,
            silo=doc.silo,
            cta_text=doc.cta_text,
            cta_url=doc.cta_url,
        )

    async def unpin_others(self, document_id: str, *, pinned_at: str | None) -> None:
        found = await self._query(_PINNED_QUERY, raw=True, id=document_id, pinnedAt=pinned_at)
        ids = _IdsResponse.model_validate_json(found.content).result
        if ids:
            await self._mutate(_Mutations.featured(ids, featured=False))

    async def any_pinned(self) -> bool:
        response = await self._query(_ANY_PINNED_QUERY)
        return _AnyPinnedResponse.model_validate_json(response.content).result

    async def pin_newest(self, *, excluding: str | None) -> bool:
        found = await self._query(_NEWEST_QUERY, raw=True, id=excluding)
        newest = _NewestResponse.model_validate_json(found.content).result
        if newest is None or not newest.ids:
            return False
        await self._mutate(_Mutations.featured(newest.ids, featured=True))
        return True

    async def _query(
        self, query: str, *, raw: bool = False, **params: str | None
    ) -> httpx.Response:
        """`raw` reads drafts too, which needs the token."""
        query_params = {"query": query} | {f"${k}": json.dumps(v) for k, v in params.items()}
        headers: dict[str, str] = {}
        if raw:
            query_params["perspective"] = "raw"
            headers["Authorization"] = f"Bearer {self._write_token}"
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.get(self._url, params=query_params, headers=headers)
        response.raise_for_status()
        return response

    async def _mutate(self, body: _Mutations) -> None:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            response = await client.post(
                self._mutate_url,
                content=body.model_dump_json(by_alias=True),
                headers={
                    "Authorization": f"Bearer {self._write_token}",
                    "content-type": "application/json",
                },
            )
        response.raise_for_status()
