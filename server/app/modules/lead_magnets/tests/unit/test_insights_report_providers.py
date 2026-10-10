"""The Sanity reader, the Sanity webhook signature guard, and the Webflow card
mapping, each against recorded response shapes through `httpx.MockTransport`.
The Webflow collection below is a trimmed copy of the live Reports schema."""

import base64
import functools
import hashlib
import hmac
import json
import time

import httpx
import pytest

from app.modules.lead_magnets.api.dependencies import is_valid_sanity_signature
from app.modules.lead_magnets.domain.insights_report.report import (
    LostPins,
    ReportDocument,
    ReportSource,
)
from app.modules.lead_magnets.domain.insights_report.split import split_report
from app.modules.lead_magnets.providers.sanity.article_source import SanityArticleSource
from app.modules.lead_magnets.providers.sanity.report_source import SanityReportSource
from app.modules.lead_magnets.providers.webflow.insights_cms import WebflowInsightsCms
from app.modules.lead_magnets.providers.webflow.reports_cms import WebflowReportsCms

_SANITY_REPORT = {
    "_id": "doc-1",
    "slug": "buyouts-in-the-gcc",
    "title": "Buyouts in the GCC",
    "html": "<p>Body</p>",
    "previewEnd": 5,
    "excerpt": "The eight-part playbook.",
    "publishedAt": "2026-10-05T08:00:00.000Z",
    "updatedAt": "2026-10-05T09:00:00Z",
    "coverUrl": "https://cdn.sanity.io/images/p/production/cover.jpg",
    "silo": "Buy a Business",
    "ctaText": "Get your free valuation",
    "ctaUrl": "/valuation-tool",
    "seoTitle": "GCC buyouts guide",
    "seoDescription": "Meta",
    "ogTitle": "Share",
}

_COLLECTION = {
    "fields": [
        {
            "slug": "primary-silo",
            "validations": {"options": [{"name": "Buy a Business", "id": "opt-buy"}]},
        },
        {"slug": "excerpt", "validations": None},
    ]
}


def _use_transport(monkeypatch: pytest.MonkeyPatch, handler) -> None:
    patched = functools.partial(httpx.AsyncClient, transport=httpx.MockTransport(handler))
    monkeypatch.setattr(httpx, "AsyncClient", patched)


async def test_sanity_report_is_parsed_and_cached(monkeypatch) -> None:
    requests: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"result": _SANITY_REPORT, "ms": 3})

    _use_transport(monkeypatch, handler)
    source = SanityReportSource(project_id="p", dataset="production")

    report = await source.get("buyouts-in-the-gcc")
    await source.get("buyouts-in-the-gcc")

    assert report is not None and report.silo == "Buy a Business"
    assert report.banner_pinned is False
    assert report.cover_url == "https://cdn.sanity.io/images/p/production/cover.jpg?w=1600&fm=jpg"
    assert (report.cta_text, report.cta_url) == ("Get your free valuation", "/valuation-tool")
    assert (report.seo_title, report.seo_description, report.og_title) == (
        "GCC buyouts guide",
        "Meta",
        "Share",
    )
    assert len(requests) == 1, "the second read comes from the cache"
    assert requests[0].url.host == "p.apicdn.sanity.io", "page views use the CDN quota"
    assert requests[0].url.params["$slug"] == '"buyouts-in-the-gcc"'


async def test_misses_are_cached_and_refresh_reads_fresh_into_the_cache(monkeypatch) -> None:
    hosts: list[str] = []
    published = False

    def handler(request: httpx.Request) -> httpx.Response:
        hosts.append(request.url.host)
        return httpx.Response(200, json={"result": _SANITY_REPORT if published else None})

    _use_transport(monkeypatch, handler)
    source = SanityReportSource(project_id="p", dataset="production")

    assert await source.get("buyouts-in-the-gcc") is None
    assert await source.get("buyouts-in-the-gcc") is None
    published = True
    assert await source.refresh("buyouts-in-the-gcc") is not None
    assert await source.get("buyouts-in-the-gcc") is not None
    assert hosts == ["p.apicdn.sanity.io", "p.api.sanity.io"]


def _sign(body: bytes, secret: str, timestamp: str | None = None) -> str:
    timestamp = timestamp or str(int(time.time() * 1000))
    digest = hmac.new(secret.encode(), timestamp.encode() + b"." + body, hashlib.sha256).digest()
    return f"t={timestamp},v1=" + base64.urlsafe_b64encode(digest).rstrip(b"=").decode()


def test_webhook_signature_matches_sanitys_format() -> None:
    body = json.dumps({"slug": "a"}).encode()

    assert is_valid_sanity_signature(body, _sign(body, "s3cret"), "s3cret")
    assert not is_valid_sanity_signature(body, _sign(body, "other"), "s3cret")
    assert not is_valid_sanity_signature(body + b" ", _sign(body, "s3cret"), "s3cret")
    assert not is_valid_sanity_signature(body, None, "s3cret")
    assert not is_valid_sanity_signature(body, "garbage", "s3cret")
    assert not is_valid_sanity_signature(body, _sign(body, ""), "")


def test_a_signature_older_than_ten_minutes_is_a_replay() -> None:
    body = b'{"slug": "a"}'
    now_ms = int(time.time() * 1000)
    eleven_minutes_ago = str(now_ms - 11 * 60 * 1000)
    one_retry_later = str(now_ms - 60 * 1000)

    assert not is_valid_sanity_signature(body, _sign(body, "s", eleven_minutes_ago), "s")
    assert is_valid_sanity_signature(body, _sign(body, "s", one_retry_later), "s")


def _webflow_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v2/collections/reports":
        return httpx.Response(200, json=_COLLECTION)
    raise AssertionError(f"unexpected {request.method} {request.url}")


async def test_card_fills_every_required_webflow_field(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow_handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")
    report = ReportDocument(
        document_id="doc-1",
        slug="buyouts-in-the-gcc",
        title="Buyouts in the GCC",
        html="<p>" + "w " * 450 + "</p>",
        excerpt="The <b>eight-part</b> playbook.",
        cover_url="https://cdn.sanity.io/cover.jpg",
        silo="Buy a Business",
        cta_text="Get your free valuation",
        cta_url="/valuation-tool",
        banner_pinned=True,
    )

    data = (await cms.field_data(report)).model_dump(mode="json", by_alias=True, exclude_none=True)

    for required in ("name", "slug", "excerpt"):
        assert data[required], required
    for insights_only in ("content-type", "gated", "author", "body-content"):
        assert insights_only not in data, insights_only
    assert "featured" not in data, "the top of /reports is the newest card, never pinned from here"
    assert data["pin-to-banner"] is True
    assert data["seo-title"] == data["og-title"] == "Buyouts in the GCC"
    assert data["reading-time"] == "3 min read"
    assert data["primary-silo"] == "opt-buy"
    assert data["featured-image"]["url"] == "https://cdn.sanity.io/cover.jpg"
    assert data["cta-text"] == "Get your free valuation"
    assert data["cta-url"] == "/valuation-tool"


async def test_a_report_needs_only_a_title_and_its_html(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow_handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")

    data = (
        await cms.field_data(
            ReportDocument(
                document_id="doc-1", slug="r", title="Buyouts in the GCC", html="<p>x</p>"
            )
        )
    ).model_dump(by_alias=True, exclude_none=True)

    assert "excerpt" not in data
    assert data["seo-description"] == "Buyouts in the GCC", "meta tags must never be blank"


async def test_the_editors_seo_overrides_win_over_the_title_and_excerpt(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow_handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")
    report = ReportDocument(
        document_id="doc-1",
        slug="r",
        title="T",
        html="<p>x</p>",
        excerpt="E",
        seo_title="SEO",
        seo_description="Meta",
        og_title="Share",
    )

    data = (await cms.field_data(report)).model_dump(by_alias=True)

    assert (data["seo-title"], data["seo-description"], data["og-title"]) == (
        "SEO",
        "Meta",
        "Share",
    )


async def test_an_unknown_silo_is_left_out_not_guessed(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow_handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")
    report = ReportDocument(
        document_id="doc-1", slug="x", title="X", html="", excerpt="E", silo="Nowhere"
    )

    data = (await cms.field_data(report)).model_dump(by_alias=True, exclude_none=True)

    assert "primary-silo" not in data
    assert "cta-text" not in data and "cta-url" not in data, "no button means none is written"
    assert data["pin-to-banner"] is False, "the pin is always written, so Webflow matches Sanity"


async def test_writes_go_to_the_live_endpoints_with_typed_bodies(monkeypatch) -> None:
    sent: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return _webflow_handler(request)
        sent.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(202, json={"id": "new-item"})

    _use_transport(monkeypatch, handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")
    report = ReportDocument(document_id="doc-1", slug="r", title="R", html="", excerpt="E")

    assert await cms.create(report) == "new-item"
    await cms.unpin("lbo", ("banner",))
    await cms.unpublish("item-1")

    assert sent[0][:2] == ("POST", "/v2/collections/reports/items/live")
    assert sent[0][2]["isDraft"] is False and sent[0][2]["fieldData"]["slug"] == "r"
    assert sent[1] == (
        "PATCH",
        "/v2/collections/reports/items/lbo/live",
        {"fieldData": {"pin-to-banner": False}},
    ), "the unpin must not change the card's draft state"
    assert sent[2][:2] == ("DELETE", "/v2/collections/reports/items/item-1/live")


async def test_an_update_writes_the_staged_card_then_publishes_it(monkeypatch) -> None:
    """Found in prod: the `/live` update 409s on a card an earlier sync unpublished."""
    sent: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return _webflow_handler(request)
        sent.append((request.method, request.url.path, json.loads(request.content)))
        return httpx.Response(202, json={"publishedItemIds": ["item-1"], "errors": []})

    _use_transport(monkeypatch, handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")

    await cms.update(
        "item-1",
        ReportDocument(document_id="doc-1", slug="r", title="R", html="", excerpt="E"),
    )

    assert sent[0][:2] == ("PATCH", "/v2/collections/reports/items/item-1")
    assert sent[0][2]["isDraft"] is False
    assert sent[1] == ("POST", "/v2/collections/reports/items/publish", {"itemIds": ["item-1"]})


async def test_an_update_webflow_did_not_publish_is_an_error(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return _webflow_handler(request)
        return httpx.Response(202, json={"publishedItemIds": [], "errors": ["nope"]})

    _use_transport(monkeypatch, handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")

    with pytest.raises(RuntimeError):
        await cms.update(
            "item-1",
            ReportDocument(document_id="doc-1", slug="r", title="R", html="", excerpt="E"),
        )


@pytest.mark.parametrize("status", [404, 409])
async def test_unpinning_a_card_that_is_not_live_is_not_an_error(monkeypatch, status) -> None:
    """An unpublished report's draft can still hold the tick, so its card can be the loser."""
    _use_transport(monkeypatch, lambda request: httpx.Response(status, json={}))

    await WebflowReportsCms(token="t", collection_id="reports").unpin("item-1", ("banner",))


async def test_unpinning_still_raises_on_other_errors(monkeypatch) -> None:
    _use_transport(monkeypatch, lambda request: httpx.Response(500, json={}))

    with pytest.raises(httpx.HTTPStatusError):
        await WebflowReportsCms(token="t", collection_id="reports").unpin("item-1", ("banner",))


async def test_unpublishing_a_card_that_is_not_live_is_not_an_error(monkeypatch) -> None:
    _use_transport(monkeypatch, lambda request: httpx.Response(404, json={}))

    await WebflowReportsCms(token="t", collection_id="reports").unpublish("item-1")


async def test_find_ignores_a_card_whose_slug_does_not_match(monkeypatch) -> None:
    """Never trust the list filter: a loose match must not become the card we overwrite."""

    def handler(request: httpx.Request) -> httpx.Response:
        items = [{"id": "other", "fieldData": {"slug": "other-report"}}]
        return httpx.Response(200, json={"items": items, "pagination": {"total": 1}})

    _use_transport(monkeypatch, handler)
    cms = WebflowReportsCms(token="t", collection_id="reports")

    assert await cms.find("buyouts-in-the-gcc") is None


async def test_the_report_cache_is_bounded(monkeypatch) -> None:
    from app.modules.lead_magnets.providers.sanity import report_source

    monkeypatch.setattr(report_source, "_CACHE_MAX", 3)
    _use_transport(monkeypatch, lambda request: httpx.Response(200, json={"result": None}))
    source = SanityReportSource(project_id="p", dataset="production")

    for n in range(10):
        await source.get(f"scan-{n}")

    assert list(source._cache) == ["scan-7", "scan-8", "scan-9"]


async def test_readers_only_ever_get_the_flattened_html(monkeypatch) -> None:
    """An unrendered bundle is a loader page with the whole report in a
    script tag; until it is rendered, the report is not served at all."""
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params["query"])
        return httpx.Response(200, json={"result": {**_SANITY_REPORT, "html": None}})

    _use_transport(monkeypatch, handler)
    report = await SanityReportSource(project_id="p", dataset="production").get("r")

    assert report is None
    assert '"html": renderedHtml' in queries[0]


async def test_source_reads_the_pasted_html_and_its_rendered_version(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.host == "p.api.sanity.io", "never the possibly-stale CDN"
        result = {"_id": "doc-1", "_rev": "r1", "html": "<p>raw</p>", "renderedFrom": "abc"}
        return httpx.Response(200, json={"result": result})

    _use_transport(monkeypatch, handler)
    source = await SanityReportSource(project_id="p", dataset="production").source("r")

    assert source is not None
    assert (source.document_id, source.revision, source.rendered_from) == ("doc-1", "r1", "abc")


async def test_source_carries_the_editors_lock_settings(monkeypatch) -> None:
    paragraphs = [
        {"_type": "block", "children": [{"text": f"Para {n} " + "w " * 20}]} for n in range(1, 9)
    ]
    docs = iter(
        [
            {"_id": "d", "_rev": "r", "html": "<p>x</p>", "freePages": 3, "lockedPercent": 75},
            {
                "_id": "d",
                "_rev": "r",
                "bodyFormat": "rich",
                "body": paragraphs,
                "lockedPercent": 50,
            },
        ]
    )
    queries: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        queries.append(request.url.params["query"])
        return httpx.Response(200, json={"result": next(docs)})

    _use_transport(monkeypatch, handler)
    reports = SanityReportSource(project_id="p", dataset="production")

    pasted = await reports.source("r")
    rich = await reports.source("r")

    assert pasted is not None and pasted.free_pages == 3
    assert "coalesce(freePages, 1)" in queries[0] and "coalesce(lockedPercent, 75)" in queries[0]
    assert rich is not None
    preview, _ = split_report(rich.html)
    assert "Para 4 " in preview and "Para 5 " not in preview, "50% locked opens half"


async def test_unpin_others_unticks_the_banner_in_one_transaction(
    monkeypatch,
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "GET":
            pinned = [
                {"_id": "lbo", "slug": "lbo", "bannerPinned": True},
                {"_id": "drafts.lbo", "slug": "lbo", "bannerPinned": True},
                {"_id": "exit", "slug": "exit", "bannerPinned": None},
            ]
            return httpx.Response(200, json={"result": pinned})
        return httpx.Response(200, json={})

    _use_transport(monkeypatch, handler)
    store = SanityReportSource(project_id="p", dataset="production", write_token="tok")

    lost = await store.unpin_others(["banner"], "doc-1", pinned_at="2026-10-07T10:00:00Z")

    assert lost == [LostPins(slug="lbo", pins=("banner",))], "exit holds no banner pin"
    query = sent[0].url.params
    assert query["perspective"] == "raw", "drafts must be unticked too"
    assert sent[0].headers["authorization"] == "Bearer tok"
    assert json.loads(query["$id"]) == "doc-1", "matched by id, so a renamed draft is still ours"
    assert 'path("versions.**")' in query["query"], "release versions are the editor's"
    assert json.loads(query["$pinnedAt"]) == "2026-10-07T10:00:00Z"
    assert json.loads(sent[1].content) == {
        "mutations": [
            {"patch": {"id": "lbo", "set": {"bannerPinned": False}}},
            {"patch": {"id": "drafts.lbo", "set": {"bannerPinned": False}}},
        ]
    }


async def test_unpin_others_counts_a_draft_and_its_report_as_one_card(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            pinned = [
                {"_id": "lbo", "slug": "lbo", "bannerPinned": True},
                {"_id": "drafts.lbo", "slug": "lbo", "bannerPinned": True},
            ]
            return httpx.Response(200, json={"result": pinned})
        return httpx.Response(200, json={})

    _use_transport(monkeypatch, handler)
    store = SanityReportSource(project_id="p", dataset="production", write_token="tok")

    lost = await store.unpin_others(["banner"], "doc-1", pinned_at=None)

    assert lost == [LostPins(slug="lbo", pins=("banner",))]


async def test_unpin_others_writes_nothing_when_no_other_report_is_pinned(monkeypatch) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"result": []})

    _use_transport(monkeypatch, handler)
    store = SanityReportSource(project_id="p", dataset="production", write_token="tok")

    assert await store.unpin_others(["banner"], "doc-1", pinned_at=None) == []
    assert [r.method for r in sent] == ["GET"]


async def test_save_rendered_is_guarded_by_the_revision_it_read(monkeypatch) -> None:
    sent: list[httpx.Request] = []
    status = 200

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(status, json={})

    _use_transport(monkeypatch, handler)
    store = SanityReportSource(project_id="p", dataset="production", write_token="tok")
    read = ReportSource(document_id="doc-1", revision="r1", html="<p>raw</p>", rendered_from=None)

    assert await store.save_rendered(read, html="<p>flat</p>", preview_end=3, rendered_from="abc")
    status = 409
    assert not await store.save_rendered(read, html="<p>x</p>", preview_end=1, rendered_from="d")

    request = sent[0]
    assert request.url.path == "/v2025-02-19/data/mutate/production"
    assert request.headers["authorization"] == "Bearer tok"
    assert json.loads(request.content) == {
        "mutations": [
            {
                "patch": {
                    "id": "doc-1",
                    "ifRevisionID": "r1",
                    "set": {
                        "renderedHtml": "<p>flat</p>",
                        "renderedPreviewEnd": 3,
                        "renderedFrom": "abc",
                    },
                }
            }
        ]
    }


async def test_article_unpin_others_unticks_drafts_too_in_one_transaction(monkeypatch) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        if request.method == "GET":
            return httpx.Response(200, json={"result": ["lbo", "drafts.lbo"]})
        return httpx.Response(200, json={})

    _use_transport(monkeypatch, handler)
    articles = SanityArticleSource(project_id="p", dataset="production", write_token="tok")

    await articles.unpin_others("doc-1", pinned_at="2026-10-10T10:00:00Z")

    query = sent[0].url.params
    assert query["perspective"] == "raw" and sent[0].headers["authorization"] == "Bearer tok"
    assert json.loads(query["$id"]) == "doc-1"
    assert json.loads(query["$pinnedAt"]) == "2026-10-10T10:00:00Z"
    assert 'path("versions.**")' in query["query"], "release versions are the editor's"
    assert sent[1].url.path == "/v2025-02-19/data/mutate/production"
    assert json.loads(sent[1].content) == {
        "mutations": [
            {"patch": {"id": "lbo", "set": {"featured": False}}},
            {"patch": {"id": "drafts.lbo", "set": {"featured": False}}},
        ]
    }


async def test_article_unpin_others_writes_nothing_when_no_other_article_is_pinned(
    monkeypatch,
) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"result": []})

    _use_transport(monkeypatch, handler)

    await SanityArticleSource(project_id="p", dataset="production").unpin_others(
        "doc-1", pinned_at=None
    )

    assert [r.method for r in sent] == ["GET"]


def _live(*items: dict, total: int | None = None) -> httpx.Response:
    return httpx.Response(
        200, json={"items": list(items), "pagination": {"total": total or len(items)}}
    )


def _item(item_id: str, **fields) -> dict:
    return {"id": item_id, "fieldData": {"slug": item_id, **fields}}


async def test_webflow_unpin_others_reads_every_live_page_and_spares_the_winner(
    monkeypatch,
) -> None:
    patched: list[tuple[str, dict]] = []
    first = [_item(f"i{n}") for n in range(99)] + [_item("hand", featured=True)]

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            assert request.url.path == "/v2/collections/insights/items/live"
            if request.url.params["offset"] == "0":
                return _live(*first, total=102)
            return _live(_item("win", featured=True), _item("gone", featured=True), total=102)
        patched.append((request.url.path, json.loads(request.content)))
        status = 409 if "gone" in request.url.path else 200
        return httpx.Response(status, json={})

    _use_transport(monkeypatch, handler)

    await WebflowInsightsCms(token="t", collection_id="insights").unpin_others("win")

    assert patched == [
        ("/v2/collections/insights/items/hand/live", {"fieldData": {"featured": False}}),
        ("/v2/collections/insights/items/gone/live", {"fieldData": {"featured": False}}),
    ], "a hand-written pin is cleared too; an item gone from the live site is no error"
