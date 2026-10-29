"""Sanity implementation of `ArticleSourcePort`.

Read only by the publish webhook, so it always uses the uncached API host: the
CDN can still serve the old document just after a publish. Editors pick rich
text or pasted HTML per article (`bodyFormat`); either way every rich-text
field arrives here and leaves as sanitized HTML.

Its only write unticks the `/insights` pin on other articles, with the write
token. Each one fires that article's webhook, whose sync then updates Webflow.
"""

import json
import logging
from typing import Literal

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.modules.lead_magnets.domain.insights_article.article import (
    ArticleDocument,
    PendingExhibits,
)
from app.modules.lead_magnets.providers.sanity.assets import upload_image
from app.modules.lead_magnets.providers.sanity.images import resized
from app.modules.lead_magnets.providers.sanity.portable_text import (
    Block,
    ExhibitBlock,
    Exhibits,
    sanitize,
    to_html,
)
from app.modules.lead_magnets.providers.sanity.report_source import API_VERSION

logger = logging.getLogger(__name__)

# An exported article is a few MB; the cap only stops a runaway file filling memory.
_HTML_FILE_MAX_BYTES = 20_000_000
_RICH = '[]{..., _type == "image" => {"url": asset->url}}'
_QUERY = (
    '*[_type == "insights" && slug.current == $slug][0]{'
    '_id, _rev, featured, "slug": slug.current, title, contentType, excerpt, bodyFormat, '
    f'"body": body{_RICH}, bodyHtml, "keyTakeaways": keyTakeaways{_RICH}, keyTakeawaysHtml, '
    f'"faq": faq{_RICH}, faqHtml, h1, seoTitle, seoDescription, ogTitle, targetKeyword, '
    'publishedAt, "updatedAt": _updatedAt, "coverUrl": cover.asset->url, author, silo, '
    '"ctaText": cta.text, "ctaUrl": cta.url, '
    '"htmlFileUrl": htmlFile.asset->url, exhibitImages}'
)
# Raw perspective, so open drafts are unticked too; publishing one must not re-pin it.
_PINNED_QUERY = (
    '*[_type == "insights" && featured == true'
    ' && !(_id in [$id, "drafts." + $id]) && !(_id in path("versions.**"))'
    " && ($pinnedAt == null || dateTime(_updatedAt) <= dateTime($pinnedAt))]._id"
)


class _Still(BaseModel):
    """A chart's captured still, valid only for the file it was taken from."""

    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    key: str = Field(default="", alias="_key")
    exhibit_id: str = Field(alias="exhibitId")
    bundle_url: str = Field(alias="bundleUrl")
    url: str


class _SanityArticle(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)

    id: str = Field(alias="_id")
    rev: str = Field(default="", alias="_rev")
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
    html_file_url: str | None = Field(default=None, alias="htmlFileUrl")
    exhibit_images: list[_Still] | None = Field(default=None, alias="exhibitImages")

    def exhibit_ids(self) -> list[str]:
        """Each chart in the body once, in page order; only a rich body has them."""
        if self.body_format != "rich":
            return []
        found = (b.exhibit_id for b in self.body or [] if isinstance(b, ExhibitBlock))
        return list(dict.fromkeys(found))

    def stills(self, bundle_url: str) -> dict[str, str]:
        return {
            s.exhibit_id: s.url for s in self.exhibit_images or [] if s.bundle_url == bundle_url
        }

    def html(
        self,
        blocks: list[Block] | None,
        pasted: str | None,
        exhibits: Exhibits | None = None,
    ) -> str | None:
        """The field in the editor's chosen format; the other one is ignored even if filled."""
        if self.body_format != "rich":
            html = sanitize(pasted) if pasted else ""
        else:
            html = to_html(blocks, exhibits) if blocks else ""
        # Judged after cleaning: a paste that was only a script or a table is empty.
        return html if html.strip() else None


class _QueryResponse(BaseModel):
    result: _SanityArticle | None = None


class _IdsResponse(BaseModel):
    result: list[str]


class _Featured(BaseModel):
    featured: bool


class _Stills(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    exhibit_images: list[_Still] = Field(alias="exhibitImages")


class _Patch(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    # Sanity rejects the patch (409) if the document moved on since it was read.
    if_revision_id: str | None = Field(default=None, alias="ifRevisionID")
    set_: _Featured | _Stills = Field(alias="set")


class _PatchMutation(BaseModel):
    patch: _Patch


class _Mutations(BaseModel):
    mutations: list[_PatchMutation]

    @classmethod
    def unpinned(cls, ids: list[str]) -> "_Mutations":
        return cls(
            mutations=[
                _PatchMutation(patch=_Patch(id=i, set_=_Featured(featured=False))) for i in ids
            ]
        )


class SanityArticleSource:
    def __init__(
        self, *, project_id: str, dataset: str, write_token: str = "", timeout_s: float = 30.0
    ) -> None:
        host = f"https://{project_id}.api.sanity.io/{API_VERSION}/data"
        self._url = f"{host}/query/{dataset}"
        self._mutate_url = f"{host}/mutate/{dataset}"
        self._files_url = f"https://cdn.sanity.io/files/{project_id}/{dataset}/"
        self._assets_url = f"https://{project_id}.api.sanity.io/{API_VERSION}/assets"
        self._dataset = dataset
        self._write_token = write_token
        self._timeout_s = timeout_s

    async def get(self, slug: str) -> ArticleDocument | None:
        response = await self._query(_QUERY, slug=slug)
        doc = _QueryResponse.model_validate_json(response.content).result
        if doc is None:
            return None
        exhibits = self._exhibits(doc)
        body = doc.html(doc.body, doc.body_html, exhibits)
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

    async def pending_exhibits(self, slug: str) -> PendingExhibits | None:
        response = await self._query(_QUERY, slug=slug)
        doc = _QueryResponse.model_validate_json(response.content).result
        url = self._own_file(doc.html_file_url) if doc else None
        if doc is None or url is None:
            return None
        stills = doc.stills(url)
        missing = tuple(i for i in doc.exhibit_ids() if i not in stills)
        if not missing:
            return None
        return PendingExhibits(
            document_id=doc.id, revision=doc.rev, bundle_url=url, ids=missing, stills=stills
        )

    async def bundle(self, pending: PendingExhibits) -> str:
        """Raises, not None: a failed fetch stops the sync before it writes a half-built page."""
        async with httpx.AsyncClient(timeout=self._timeout_s, follow_redirects=False) as client:
            response = await client.get(pending.bundle_url)
        response.raise_for_status()
        if len(response.content) > _HTML_FILE_MAX_BYTES:
            raise ValueError(f"article html file is over {_HTML_FILE_MAX_BYTES} bytes")
        return response.content.decode("utf-8", errors="replace")

    async def upload_image(self, data: bytes, mime: str) -> str:
        return await upload_image(
            assets_url=self._assets_url,
            dataset=self._dataset,
            write_token=self._write_token,
            data=data,
            mime=mime,
            timeout_s=self._timeout_s,
        )

    async def save_exhibit_images(self, pending: PendingExhibits, urls: dict[str, str]) -> bool:
        stills = [
            _Still(key=i.replace("#", "-"), exhibit_id=i, bundle_url=pending.bundle_url, url=u)
            for i, u in (pending.stills | urls).items()
        ]
        patch = _Patch(
            id=pending.document_id,
            if_revision_id=pending.revision,
            set_=_Stills(exhibit_images=stills),
        )
        response = await self._post(_Mutations(mutations=[_PatchMutation(patch=patch)]))
        if response.status_code == 409:
            return False
        response.raise_for_status()
        return True

    async def unpin_others(self, document_id: str, *, pinned_at: str | None) -> None:
        found = await self._query(_PINNED_QUERY, raw=True, id=document_id, pinnedAt=pinned_at)
        ids = _IdsResponse.model_validate_json(found.content).result
        if ids:
            await self._mutate(_Mutations.unpinned(ids))

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

    def _own_file(self, url: str | None) -> str | None:
        # The browser loads this URL into a frame, so it must be this dataset's own file.
        return url if url and url.startswith(self._files_url) else None

    def _exhibits(self, doc: _SanityArticle) -> Exhibits | None:
        url = self._own_file(doc.html_file_url)
        return Exhibits(bundle_url=url, images=doc.stills(url)) if url else None

    async def _mutate(self, body: _Mutations) -> None:
        (await self._post(body)).raise_for_status()

    async def _post(self, body: _Mutations) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self._timeout_s) as client:
            return await client.post(
                self._mutate_url,
                content=body.model_dump_json(by_alias=True, exclude_none=True),
                headers={
                    "Authorization": f"Bearer {self._write_token}",
                    "content-type": "application/json",
                },
            )
