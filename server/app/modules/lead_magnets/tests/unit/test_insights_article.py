"""Insights articles from Sanity: Portable Text and pasted HTML become safe
Webflow rich text, and the sync writes only articles it created."""

import functools
import json

import httpx
import pytest
from pydantic import TypeAdapter

from app.modules.lead_magnets.application.insights_article.sync import ArticleSync
from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument, CmsItem
from app.modules.lead_magnets.providers.sanity.article_source import SanityArticleSource
from app.modules.lead_magnets.providers.sanity.portable_text import Block, sanitize, to_html
from app.modules.lead_magnets.providers.webflow.insights_cms import WebflowInsightsCms

_BLOCKS = TypeAdapter(list[Block])


def _text(text: str, *, style: str = "normal", marks: list[str] | None = None, **extra) -> dict:
    return {
        "_type": "block",
        "style": style,
        "children": [{"_type": "span", "text": text, "marks": marks or []}],
        **extra,
    }


def _item(text: str, kind: str = "bullet", level: int = 1) -> dict:
    return _text(text, listItem=kind, level=level)


def test_portable_text_becomes_the_html_hand_written_articles_use() -> None:
    blocks = _BLOCKS.validate_python(
        [
            _text("Why", style="h2"),
            _text("Bold", marks=["strong"]),
            _text("Sell", marks=["l1"], markDefs=[{"_key": "l1", "href": "/sell"}]),
            _item("one"),
            _item("nested", level=2),
            _item("two"),
            _item("first", kind="number"),
            {"_type": "image", "url": "https://cdn.sanity.io/i.png", "alt": 'a "b"'},
            _text("<script>x</script> & y"),
        ]
    )

    assert to_html(blocks) == (
        "<h2>Why</h2><p><strong>Bold</strong></p>"
        '<p><a href="/sell" rel="noopener noreferrer">Sell</a></p>'
        "<ul><li>one<ul><li>nested</li></ul></li><li>two</li></ul>"
        "<ol><li>first</li></ol>"
        '<figure><img src="https://cdn.sanity.io/i.png?w=1600&amp;fm=jpg" '
        'alt="a &quot;b&quot;"></figure>'
        "<p>&lt;script&gt;x&lt;/script&gt; &amp; y</p>"
    )


def test_pasted_html_loses_anything_that_could_run_on_the_live_site() -> None:
    """Found 2026-10-07: Webflow's API stores script tags and javascript: links verbatim."""
    html = sanitize(
        '<h2 style="color:red" onclick="x()">T</h2><script>alert(1)</script>'
        '<p><a href="javascript:alert(1)">js</a><a href="/buyers">ok</a></p>'
        "<iframe src=//evil></iframe><table><tr><td>cell</td></tr></table>"
    )

    assert "script" not in html and "javascript" not in html and "iframe" not in html
    assert "onclick" not in html and "style" not in html and "<table" not in html
    assert html.startswith("<h2>T</h2>") and 'href="/buyers"' in html


def test_every_sanity_image_is_sized_under_webflows_4mb_limit_but_others_are_left_alone() -> None:
    html = sanitize(
        '<img src="https://cdn.sanity.io/images/p/production/big.png">'
        '<img src="https://cdn.sanity.io/images/p/production/s.png?w=400">'
        '<img src="https://example.com/x.png">'
    )

    assert 'src="https://cdn.sanity.io/images/p/production/big.png?w=1600&amp;fm=jpg"' in html
    assert 'src="https://cdn.sanity.io/images/p/production/s.png?w=400"' in html
    assert 'src="https://example.com/x.png"' in html


def _use_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    patched = functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", patched)


_SANITY_ARTICLE = {
    "slug": "exit-guide",
    "title": "Exit guide",
    "contentType": "Article",
    "excerpt": "E",
    "bodyFormat": "html",
    "body": [_text("ignored rich body")],
    "bodyHtml": "<p>Pasted</p><script>x</script>",
    "keyTakeaways": None,
    "keyTakeawaysHtml": "<ul><li>Point</li></ul>",
}


async def test_the_source_reads_the_chosen_format_fresh_and_sanitized(monkeypatch) -> None:
    hosts: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(200, json={"result": _SANITY_ARTICLE})

    _use_transport(monkeypatch, handler)

    article = await SanityArticleSource(project_id="p", dataset="production").get("exit-guide")

    assert article is not None
    assert article.body_html == "<p>Pasted</p>", "HTML mode ignores the rich body and is cleaned"
    assert article.key_takeaways_html == "<ul><li>Point</li></ul>"
    assert article.faq_html is None
    assert hosts == ["p.api.sanity.io"], "the webhook must never read a stale CDN copy"


@pytest.mark.parametrize("pasted", ["", "<script>x()</script>", "<style>p { color: red }</style>"])
async def test_a_body_that_cleans_down_to_nothing_is_not_written(monkeypatch, pasted: str) -> None:
    _use_transport(
        monkeypatch,
        lambda request: httpx.Response(
            200, json={"result": {**_SANITY_ARTICLE, "bodyHtml": pasted}}
        ),
    )

    assert await SanityArticleSource(project_id="p", dataset="production").get("x") is None


_COLLECTION = {
    "fields": [
        {"slug": "content-type", "validations": {"options": [{"name": "Article", "id": "opt-a"}]}},
        {
            "slug": "primary-silo",
            "validations": {"options": [{"name": "Exit Strategy", "id": "s"}]},
        },
        {"slug": "author", "validations": {"collectionId": "team"}},
    ]
}
_TEAM = {
    "items": [{"id": "team-jules", "fieldData": {"name": "Jules Chasles"}}],
    "pagination": {"total": 1},
}


def _webflow(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v2/collections/insights":
        return httpx.Response(200, json=_COLLECTION)
    if request.url.path == "/v2/collections/team/items":
        return httpx.Response(200, json=_TEAM)
    raise AssertionError(f"unexpected {request.method} {request.url}")


def _article(**changes) -> ArticleDocument:
    fields = {
        "slug": "exit-guide",
        "title": "Exit guide",
        "content_type": "Article",
        "excerpt": "E",
        "body_html": "<p>" + "w " * 450 + "</p>",
        "author": "Jules Chasles",
        "silo": "Exit Strategy",
    }
    return ArticleDocument(**{**fields, **changes})


async def test_an_article_is_written_as_a_managed_item_that_never_touches_the_pin(
    monkeypatch,
) -> None:
    sent: list[dict] = []
    schema_reads: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/v2/collections/insights":
            schema_reads.append(1)
        if request.method == "GET":
            return _webflow(request)
        sent.append(json.loads(request.content))
        return httpx.Response(202, json={"id": "new-item"})

    _use_transport(monkeypatch, handler)
    cms = WebflowInsightsCms(token="t", collection_id="insights")

    assert await cms.create(_article()) == "new-item"

    data = sent[0]["fieldData"]
    assert sent[0]["isDraft"] is False
    assert data["sanity-managed"] is True
    assert (data["content-type"], data["author"], data["primary-silo"]) == (
        "opt-a",
        "team-jules",
        "s",
    )
    assert data["seo-title"] == data["og-title"] == data["h1-tag"] == "Exit guide"
    assert data["seo-description"] == "E"
    assert (data["reading-time"], data["word-count"]) == ("3 min read", 450)
    for hand_set in ("featured", "hide-from-listings", "gated"):
        assert hand_set not in data, f"{hand_set} is set in Webflow, never by the sync"
    assert len(schema_reads) == 1, "one schema read serves every id lookup"


async def test_takeaways_and_faq_get_the_heading_hand_written_articles_carry(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow)
    cms = WebflowInsightsCms(token="t", collection_id="insights")

    data = await cms.field_data(
        _article(key_takeaways_html="<ul><li>A</li></ul>", faq_html="<h2>Questions</h2><p>Q</p>")
    )

    assert data.key_takeaways == "<h2>Key Takeaways</h2><ul><li>A</li></ul>"
    assert data.faq_content == "<h2>Questions</h2><p>Q</p>", "an editor's own heading is kept"


async def test_an_unknown_content_type_fails_by_name(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow)
    cms = WebflowInsightsCms(token="t", collection_id="insights")

    with pytest.raises(ValueError, match="Report"):
        await cms.field_data(_article(content_type="Report"))


async def test_find_reports_whether_the_sync_owns_the_item(monkeypatch) -> None:
    items = [
        {"id": "mine", "fieldData": {"slug": "mine", "sanity-managed": True}},
        {"id": "hand", "fieldData": {"slug": "hand", "sanity-managed": None}},
    ]
    _use_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"items": items, "pagination": {"total": 2}}),
    )
    cms = WebflowInsightsCms(token="t", collection_id="insights")

    assert await cms.find("mine") == CmsItem(id="mine", managed=True)
    assert await cms.find("hand") == CmsItem(id="hand", managed=False)


class _Source:
    def __init__(self, *articles: ArticleDocument) -> None:
        self._articles = {a.slug: a for a in articles}

    async def get(self, slug: str) -> ArticleDocument | None:
        return self._articles.get(slug)


class _Cms:
    def __init__(self, items: dict[str, CmsItem] | None = None) -> None:
        self.items = items or {}
        self.calls: list[tuple[str, str]] = []

    async def find(self, slug: str) -> CmsItem | None:
        return self.items.get(slug)

    async def create(self, article: ArticleDocument) -> str:
        self.calls.append(("create", article.slug))
        return "new"

    async def update(self, item_id: str, article: ArticleDocument) -> None:
        self.calls.append(("update", item_id))

    async def unpublish(self, item_id: str) -> None:
        self.calls.append(("unpublish", item_id))


async def _sync(cms: _Cms, *articles: ArticleDocument, slug: str | None, previous: str | None):
    await ArticleSync(source=_Source(*articles), cms=cms).sync(slug=slug, previous_slug=previous)


async def test_a_new_article_is_created_and_a_managed_one_updated() -> None:
    cms = _Cms({"other": CmsItem(id="item-2", managed=True)})
    await _sync(cms, _article(), slug="exit-guide", previous=None)
    await _sync(cms, _article(slug="other"), slug="other", previous=None)

    assert cms.calls == [("create", "exit-guide"), ("update", "item-2")]


async def test_a_hand_written_article_with_the_same_slug_is_never_touched() -> None:
    cms = _Cms({"exit-guide": CmsItem(id="hand", managed=False)})
    await _sync(cms, _article(), slug="exit-guide", previous=None)
    await _sync(cms, slug=None, previous="exit-guide")

    assert cms.calls == []


async def test_unpublishing_or_renaming_takes_down_only_the_managed_item() -> None:
    cms = _Cms({"old": CmsItem(id="item-1", managed=True)})
    await _sync(cms, _article(slug="new"), slug="new", previous="old")
    await _sync(cms, slug=None, previous="new")

    assert cms.calls == [("unpublish", "item-1"), ("create", "new")]
