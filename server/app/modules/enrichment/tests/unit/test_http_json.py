"""Coverage for `fetch_json` — the fail-soft GET helper shared by Diffbot
and People Data Labs, extracted out of both clients since it was
byte-identical control flow. No real network call: `aiohttp.ClientSession`
is monkeypatched via the shared `tests.aiohttp_fakes` helper.
"""

import aiohttp

from app.modules.enrichment.providers.http_json import fetch_json
from tests.aiohttp_fakes import FakeAiohttpResponse, FakeAiohttpSession, patch_aiohttp_session


async def test_fetch_json_returns_body_on_200(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch, FakeAiohttpSession(get=FakeAiohttpResponse(200, {"hello": "world"}))
    )

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result == {"hello": "world"}


async def test_fetch_json_returns_none_on_non_200(monkeypatch) -> None:
    # Body is never read on a non-200 — `fetch_json` returns before calling
    # `.json()` — so an empty dict stands in for "no body".
    patch_aiohttp_session(monkeypatch, FakeAiohttpSession(get=FakeAiohttpResponse(500, {})))

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result is None


async def test_fetch_json_returns_none_on_connection_error(monkeypatch) -> None:
    patch_aiohttp_session(monkeypatch, FakeAiohttpSession(get=ConnectionError("boom")))

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result is None
