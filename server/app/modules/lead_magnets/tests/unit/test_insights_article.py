"""Insights articles from Sanity: Portable Text and pasted HTML become safe
Webflow rich text, and the sync writes only articles it created."""

import functools
import json

import httpx
import pytest
from pydantic import TypeAdapter

from app.modules.lead_magnets.application.insights_article.sync import ArticleSync
from app.modules.lead_magnets.domain.insights_article.article import ArticleDocument, CmsItem
from app.modules.lead_magnets.domain.insights_report.split import split_report
from app.modules.lead_magnets.providers.sanity.article_source import SanityArticleSource
from app.modules.lead_magnets.providers.sanity.portable_text import (
    Block,
    rich_report,
    sanitize,
    to_html,
)
from app.modules.lead_magnets.providers.sanity.report_source import SanityReportSource
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


def test_every_studio_style_and_mark_reaches_webflow() -> None:
    marks = ["underline", "strike-through", "code", "sup", "sub"]
    blocks = _BLOCKS.validate_python(
        [
            _text("Five", style="h5"),
            _text("Six", style="h6"),
            *(_text(mark, marks=[mark]) for mark in marks),
            _text(
                "Out",
                marks=["l1"],
                markDefs=[{"_key": "l1", "href": "https://x.io", "blank": True}],
            ),
        ]
    )

    assert to_html(blocks) == (
        "<h5>Five</h5><h6>Six</h6><p><u>underline</u></p><p><s>strike-through</s></p>"
        "<p><code>code</code></p><p><sup>sup</sup></p><p><sub>sub</sub></p>"
        '<p><a href="https://x.io" target="_blank" rel="noopener noreferrer">Out</a></p>'
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
    "_id": "doc-1",
    "featured": None,
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
    assert (article.document_id, article.featured) == ("doc-1", False)
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
        "document_id": "doc-1",
        "author": "Jules Chasles",
        "silo": "Exit Strategy",
    }
    return ArticleDocument(**{**fields, **changes})


async def test_an_article_is_written_as_a_managed_item_with_its_pin(
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

    assert await cms.create(_article(featured=True)) == "new-item"

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
    assert data["featured"] is True
    for hand_set in ("hide-from-listings", "gated"):
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
        {"id": "hand", "fieldData": {"slug": "hand", "sanity-managed": None, "featured": True}},
    ]
    _use_transport(
        monkeypatch,
        lambda request: httpx.Response(200, json={"items": items, "pagination": {"total": 2}}),
    )
    cms = WebflowInsightsCms(token="t", collection_id="insights")

    assert await cms.find("mine") == CmsItem(id="mine", managed=True)
    assert await cms.find("hand") == CmsItem(id="hand", managed=False, featured=True)


class _Source:
    def __init__(
        self,
        *articles: ArticleDocument,
        others_pinned: bool = False,
        newest: list[str] | None = None,
    ) -> None:
        self._articles = {a.slug: a for a in articles}
        self.others_pinned = others_pinned
        # Published article ids, newest first.
        self.newest = newest or []
        self.calls: list[tuple[str, str | None]] = []

    async def get(self, slug: str) -> ArticleDocument | None:
        return self._articles.get(slug)

    async def unpin_others(self, document_id: str, *, pinned_at: str | None) -> None:
        self.calls.append(("unpin_others", f"{document_id}@{pinned_at}"))

    async def any_pinned(self) -> bool:
        return self.others_pinned or any(a.featured for a in self._articles.values())

    async def pin_newest(self, *, excluding: str | None) -> bool:
        newest = next((i for i in self.newest if i != excluding), None)
        if newest:
            self.calls.append(("pin", newest))
        return newest is not None


class _Cms:
    def __init__(
        self,
        items: dict[str, CmsItem] | None = None,
        *,
        live_pin: bool = False,
        hand_written: str | None = None,
    ) -> None:
        self.items = items or {}
        self.live_pin = live_pin
        self.hand_written = hand_written
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

    async def unpin_others(self, keep_id: str) -> None:
        self.calls.append(("unpin_others", keep_id))

    async def any_pinned(self) -> bool:
        return self.live_pin

    async def newest_hand_written(self) -> str | None:
        return self.hand_written

    async def pin(self, item_id: str) -> None:
        self.calls.append(("pin", item_id))


async def _sync(
    cms: _Cms,
    *articles: ArticleDocument,
    slug: str | None,
    previous: str | None,
    source: _Source | None = None,
):
    source = source or _Source(*articles)
    await ArticleSync(source=source, cms=cms).sync(slug=slug, previous_slug=previous)


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


_PINNED = CmsItem(id="item-1", managed=True, featured=True)


async def test_a_pinned_article_takes_the_pin_from_every_item_then_from_sanity() -> None:
    cms = _Cms({"exit-guide": CmsItem(id="item-1", managed=True)})
    source = _Source(_article(featured=True, updated_at="t1"))

    await _sync(cms, source=source, slug="exit-guide", previous=None)

    assert cms.calls == [("update", "item-1"), ("unpin_others", "item-1")]
    assert source.calls == [("unpin_others", "doc-1@t1")], "the later of two pins wins"


async def test_a_new_pinned_article_takes_the_pin_once_it_is_live() -> None:
    cms = _Cms()

    await _sync(cms, _article(featured=True), slug="exit-guide", previous=None)

    assert cms.calls == [("create", "exit-guide"), ("unpin_others", "new")]


async def test_unpinning_hands_the_pin_to_the_newest_other_sanity_article() -> None:
    cms = _Cms({"exit-guide": _PINNED}, hand_written="hand-1")
    source = _Source(_article(), newest=["doc-1", "doc-2"])

    await _sync(cms, source=source, slug="exit-guide", previous=None)

    assert source.calls == [("pin", "doc-2")], "never straight back to the article just unpinned"
    assert cms.calls == [("update", "item-1")], "doc-2's own webhook pins its Webflow item"


async def test_with_no_other_sanity_article_the_newest_hand_written_one_is_pinned() -> None:
    cms = _Cms({"exit-guide": _PINNED}, hand_written="hand-1")

    await _sync(cms, source=_Source(_article(), newest=["doc-1"]), slug="exit-guide", previous=None)

    assert cms.calls == [("update", "item-1"), ("pin", "hand-1")]


async def test_deleting_or_unpublishing_the_pinned_article_hands_the_pin_on() -> None:
    cms = _Cms({"exit-guide": _PINNED})
    source = _Source(newest=["doc-2"])

    await _sync(cms, source=source, slug=None, previous="exit-guide")

    assert cms.calls == [("unpublish", "item-1")]
    assert source.calls == [("pin", "doc-2")]


async def test_renaming_the_pinned_article_keeps_its_pin() -> None:
    cms = _Cms({"old": _PINNED}, hand_written="hand-1")
    source = _Source(_article(slug="new", featured=True), newest=["doc-2"])

    await _sync(cms, source=source, slug="new", previous="old")

    assert ("pin", "doc-2") not in source.calls and ("pin", "hand-1") not in cms.calls


@pytest.mark.parametrize(
    ("others_pinned", "live_pin"),
    [(True, False), (False, True)],
    ids=["another-sanity-pin", "a-hand-pinned-webflow-item"],
)
async def test_nothing_is_handed_on_while_another_pin_holds(
    others_pinned: bool, live_pin: bool
) -> None:
    """Also the losing article's own webhook, after another article took the pin."""
    cms = _Cms({"exit-guide": _PINNED}, live_pin=live_pin, hand_written="hand-1")
    source = _Source(_article(), others_pinned=others_pinned, newest=["doc-2"])

    await _sync(cms, source=source, slug="exit-guide", previous=None)

    assert source.calls == [] and cms.calls == [("update", "item-1")]


async def test_an_edit_that_never_held_the_pin_hands_nothing_on() -> None:
    cms = _Cms({"exit-guide": CmsItem(id="item-1", managed=True)}, hand_written="hand-1")
    source = _Source(_article(), newest=["doc-2"])

    await _sync(cms, source=source, slug="exit-guide", previous=None)

    assert source.calls == [] and cms.calls == [("update", "item-1")]


def _paragraphs(first: int, last: int) -> list[dict]:
    return [_text(f"Paragraph {i} " + "word " * 20) for i in range(first, last + 1)]


def test_a_rich_report_opens_its_first_quarter_and_never_cuts_a_list() -> None:
    blocks = _BLOCKS.validate_python(
        [*_paragraphs(1, 2), _item("a"), _item("b"), _item("c"), *_paragraphs(3, 12)]
    )

    page = rich_report('Buyouts <in> "GCC"', blocks)

    assert page is not None
    preview, rest = split_report(page)
    assert "<h1>Buyouts &lt;in&gt; &quot;GCC&quot;</h1>" in preview
    assert "Paragraph 2 " in preview and "Paragraph 5 " not in preview
    assert "<li>c</li></ul>" in preview, "the cut falls after the list, never inside it"
    assert "Paragraph 12 " in rest


def test_a_rich_report_opens_the_share_the_editor_set() -> None:
    blocks = _BLOCKS.validate_python(_paragraphs(1, 8))

    page = rich_report("T", blocks, share=0.5)

    assert page is not None
    preview, rest = split_report(page)
    assert "Paragraph 4 " in preview and "Paragraph 5 " not in preview
    assert "Paragraph 5 " in rest


def test_a_rich_report_with_no_text_is_not_published() -> None:
    assert rich_report("T", []) is None


async def test_reports_from_before_the_toggle_are_still_pasted_html(monkeypatch) -> None:
    # The real GROQ shape: a field the document never had comes back as null, not missing.
    doc = {
        "_id": "d",
        "_rev": "r",
        "title": "T",
        "bodyFormat": None,
        "body": None,
        "html": "<p>pasted</p>",
        "renderedFrom": None,
    }
    rich = {**doc, "bodyFormat": "rich", "body": [_text("written in Studio")]}
    responses = iter([doc, rich])
    _use_transport(
        monkeypatch, lambda request: httpx.Response(200, json={"result": next(responses)})
    )
    source = SanityReportSource(project_id="p", dataset="production")

    legacy = await source.source("t")
    written = await source.source("t")

    assert legacy is not None and legacy.html == "<p>pasted</p>"
    assert written is not None and "<p>written in Studio</p>" in written.html
    assert 'class="wusool-rich"' in written.html


async def test_an_article_with_a_null_body_format_reads_as_pasted_html(monkeypatch) -> None:
    doc = {**_SANITY_ARTICLE, "bodyFormat": None, "body": None, "bodyHtml": "<p>Pasted</p>"}
    _use_transport(monkeypatch, lambda request: httpx.Response(200, json={"result": doc}))

    article = await SanityArticleSource(project_id="p", dataset="production").get("x")

    assert article is not None and article.body_html == "<p>Pasted</p>"
