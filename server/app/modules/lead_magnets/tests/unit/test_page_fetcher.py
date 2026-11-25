"""The `/enrich` page fetch: only public https hosts, bounded, never raises."""

import httpx
import pytest

from app.modules.lead_magnets.providers.web import page_fetcher
from app.modules.lead_magnets.providers.web.page_fetcher import HttpPageFetcher

_PUBLIC = "93.184.216.34"


def _resolve(monkeypatch, mapping: dict[str, str]) -> None:
    async def fake_getaddrinfo(self, host, port, **kwargs):
        return [(2, 1, 6, "", (mapping[host], port))]

    monkeypatch.setattr("asyncio.BaseEventLoop.getaddrinfo", fake_getaddrinfo)


def _serve(monkeypatch, handler) -> None:
    real = httpx.AsyncClient
    monkeypatch.setattr(
        page_fetcher.httpx,
        "AsyncClient",
        lambda **kw: real(transport=httpx.MockTransport(handler), **kw),
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://acme.ae",
        "https://localhost",
        "https://private.test",
        "https://metadata.test",
        "https://acme.ae:8443",
    ],
)
async def test_blocks_non_https_and_non_public_hosts(monkeypatch, url) -> None:
    _resolve(
        monkeypatch,
        {"localhost": "127.0.0.1", "private.test": "10.0.0.5", "metadata.test": "169.254.169.254"},
    )
    _serve(monkeypatch, lambda request: pytest.fail("must not be requested"))

    assert await HttpPageFetcher().fetch_html(url) == ""


async def test_returns_the_body_of_a_public_page(monkeypatch) -> None:
    _resolve(monkeypatch, {"acme.ae": _PUBLIC})
    _serve(monkeypatch, lambda request: httpx.Response(200, text="<title>x</title>"))

    assert await HttpPageFetcher().fetch_html("https://acme.ae") == "<title>x</title>"


async def test_does_not_follow_a_redirect_to_a_blocked_host(monkeypatch) -> None:
    _resolve(monkeypatch, {"acme.ae": _PUBLIC, "internal.test": "10.0.0.5"})
    seen: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request.url.host)
        return httpx.Response(302, headers={"location": "https://internal.test/"})

    _serve(monkeypatch, handler)

    assert await HttpPageFetcher().fetch_html("https://acme.ae") == ""
    assert seen == ["acme.ae"]


async def test_caps_the_body_size(monkeypatch) -> None:
    _resolve(monkeypatch, {"acme.ae": _PUBLIC})
    _serve(monkeypatch, lambda request: httpx.Response(200, content=b"a" * 2_000_000))

    assert len(await HttpPageFetcher().fetch_html("https://acme.ae")) == 512 * 1024


async def test_a_failed_request_returns_empty(monkeypatch) -> None:
    _resolve(monkeypatch, {"acme.ae": _PUBLIC})

    def boom(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("down")

    _serve(monkeypatch, boom)

    assert await HttpPageFetcher().fetch_html("https://acme.ae") == ""
