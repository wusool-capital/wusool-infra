"""The Sanity reader, the Sanity webhook signature guard, and the Webflow card
mapping, each against recorded response shapes through `httpx.MockTransport`.
The Webflow collection below is a trimmed copy of the live Insights schema."""

import base64
import functools
import hashlib
import hmac
import json

import httpx
import pytest

from app.modules.lead_magnets.api.dependencies import is_valid_sanity_signature
from app.modules.lead_magnets.domain.insights_report.report import ReportDocument
from app.modules.lead_magnets.providers.sanity.report_source import SanityReportSource
from app.modules.lead_magnets.providers.webflow.insights_cms import WebflowInsightsCms

_SANITY_REPORT = {
    "slug": "buyouts-in-the-gcc",
    "title": "Buyouts in the GCC",
    "html": "<p>Body</p>",
    "excerpt": "The eight-part playbook.",
    "publishedAt": "2026-10-05T08:00:00.000Z",
    "updatedAt": "2026-10-05T09:00:00Z",
    "coverUrl": "https://cdn.sanity.io/images/p/production/cover.jpg",
    "featured": None,
    "author": "Jules Chasles",
    "silo": "Buy a Business",
}

_COLLECTION = {
    "fields": [
        {
            "slug": "content-type",
            "validations": {
                "options": [
                    {"name": "Article", "id": "opt-article"},
                    {"name": "Report", "id": "opt-report"},
                ]
            },
        },
        {
            "slug": "primary-silo",
            "validations": {"options": [{"name": "Buy a Business", "id": "opt-buy"}]},
        },
        {"slug": "author", "validations": {"collectionId": "team"}},
        {"slug": "body-content", "validations": None},
    ]
}
_TEAM = {
    "items": [{"id": "team-jules", "fieldData": {"name": "Jules Chasles"}}],
    "pagination": {"total": 1},
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

    assert report is not None and report.author == "Jules Chasles"
    assert report.featured is False
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


def _sign(body: bytes, secret: str, timestamp: str = "1791210000000") -> str:
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


def _webflow_handler(request: httpx.Request) -> httpx.Response:
    if request.url.path == "/v2/collections/insights":
        return httpx.Response(200, json=_COLLECTION)
    if request.url.path == "/v2/collections/team/items":
        return httpx.Response(200, json=_TEAM)
    raise AssertionError(f"unexpected {request.method} {request.url}")


async def test_card_fills_every_required_webflow_field(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow_handler)
    cms = WebflowInsightsCms(token="t", collection_id="insights")
    report = ReportDocument(
        slug="buyouts-in-the-gcc",
        title="Buyouts in the GCC",
        html="<p>" + "w " * 450 + "</p>",
        excerpt="The <b>eight-part</b> playbook.",
        cover_url="https://cdn.sanity.io/cover.jpg",
        author="Jules Chasles",
        silo="Buy a Business",
    )

    data = (await cms.field_data(report, featured=True)).model_dump(
        mode="json", by_alias=True, exclude_none=True
    )

    for required in ("name", "slug", "content-type", "body-content", "excerpt"):
        assert data[required], required
    assert data["content-type"] == "opt-report"
    assert data["gated"] is True and data["featured"] is True
    assert data["body-content"] == "<p>The &lt;b&gt;eight-part&lt;/b&gt; playbook.</p>"
    assert data["seo-title"] == data["og-title"] == "Buyouts in the GCC"
    assert data["reading-time"] == "3 min read"
    assert data["author"] == "team-jules"
    assert data["primary-silo"] == "opt-buy"
    assert data["featured-image"]["url"].endswith("cover.jpg?w=1600&fm=jpg")


async def test_unknown_author_and_silo_are_left_out_not_guessed(monkeypatch) -> None:
    _use_transport(monkeypatch, _webflow_handler)
    cms = WebflowInsightsCms(token="t", collection_id="insights")
    report = ReportDocument(
        slug="x", title="X", html="", excerpt="E", author="Nobody", silo="Nowhere"
    )

    data = (await cms.field_data(report)).model_dump(by_alias=True, exclude_none=True)

    assert "author" not in data and "primary-silo" not in data
    assert "featured" not in data, "no pin change means the pin isn't written at all"


async def test_featured_ids_reads_every_live_page(monkeypatch) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/v2/collections/insights/items/live"
        offset = int(request.url.params["offset"])
        items = [
            {"id": f"item-{offset + i}", "fieldData": {"featured": offset + i == 150}}
            for i in range(100 if offset == 0 else 60)
        ]
        return httpx.Response(200, json={"items": items, "pagination": {"total": 160}})

    _use_transport(monkeypatch, handler)

    assert await WebflowInsightsCms(token="t", collection_id="insights").featured_ids() == [
        "item-150"
    ]


async def test_writes_go_to_the_live_endpoints_with_typed_bodies(monkeypatch) -> None:
    sent: list[tuple[str, str, dict]] = []

    def handler(request: httpx.Request) -> httpx.Response:
        if request.method == "GET":
            return _webflow_handler(request)
        sent.append((request.method, request.url.path, json.loads(request.content or b"{}")))
        return httpx.Response(202, json={})

    _use_transport(monkeypatch, handler)
    cms = WebflowInsightsCms(token="t", collection_id="insights")
    report = ReportDocument(slug="r", title="R", html="", excerpt="E")

    await cms.create(report, featured=None)
    await cms.unfeature("lbo")
    await cms.unpublish("item-1")

    assert sent[0][:2] == ("POST", "/v2/collections/insights/items/live")
    assert sent[0][2]["isDraft"] is False and sent[0][2]["fieldData"]["slug"] == "r"
    assert sent[1] == (
        "PATCH",
        "/v2/collections/insights/items/lbo/live",
        {"fieldData": {"featured": False}},
    ), "the unpin must not change a hand-written article's draft state"
    assert sent[2][:2] == ("DELETE", "/v2/collections/insights/items/item-1/live")


async def test_find_ignores_a_card_whose_slug_does_not_match(monkeypatch) -> None:
    """Never trust the list filter: a loose match must not become the card we overwrite."""

    def handler(request: httpx.Request) -> httpx.Response:
        items = [{"id": "other", "fieldData": {"slug": "other-report", "gated": True}}]
        return httpx.Response(200, json={"items": items, "pagination": {"total": 1}})

    _use_transport(monkeypatch, handler)
    cms = WebflowInsightsCms(token="t", collection_id="insights")

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
        result = {"_id": "doc-1", "html": "<p>raw</p>", "renderedFrom": "abc"}
        return httpx.Response(200, json={"result": result})

    _use_transport(monkeypatch, handler)
    source = await SanityReportSource(project_id="p", dataset="production").source("r")

    assert source is not None
    assert (source.document_id, source.html, source.rendered_from) == ("doc-1", "<p>raw</p>", "abc")


async def test_save_rendered_patches_the_hidden_fields_with_the_write_token(monkeypatch) -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"results": [{"id": "doc-1"}]})

    _use_transport(monkeypatch, handler)
    source = SanityReportSource(project_id="p", dataset="production", write_token="tok")

    await source.save_rendered("doc-1", "<p>flat</p>", "abc")

    (request,) = sent
    assert request.method == "POST"
    assert request.url.path == "/v2025-02-19/data/mutate/production"
    assert request.headers["authorization"] == "Bearer tok"
    assert json.loads(request.content) == {
        "mutations": [
            {
                "patch": {
                    "id": "doc-1",
                    "set": {"renderedHtml": "<p>flat</p>", "renderedFrom": "abc"},
                }
            }
        ]
    }
