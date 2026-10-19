"""Coverage for `fetch_json` — the fail-soft GET helper shared by Diffbot
and People Data Labs, extracted out of both clients since it was
byte-identical control flow. No real network call: `aiohttp.ClientSession`
is monkeypatched via the shared `tests.aiohttp_fakes` helper.
"""

import aiohttp

from app.modules.enrichment.providers.http_json import fetch_json, post_json_array
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


async def test_fetch_json_retries_once_on_short_retry_after(monkeypatch) -> None:
    session = FakeAiohttpSession(
        get=[
            FakeAiohttpResponse(429, {}, headers={"Retry-After": "0"}),
            FakeAiohttpResponse(200, {"ok": True}),
        ]
    )
    patch_aiohttp_session(monkeypatch, session)

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result == {"ok": True}
    assert session.get_calls == 2


async def test_fetch_json_gives_up_on_long_retry_after_and_logs_rate_limit(
    monkeypatch, caplog
) -> None:
    session = FakeAiohttpSession(get=FakeAiohttpResponse(429, {}, headers={"Retry-After": "60"}))
    patch_aiohttp_session(monkeypatch, session)

    with caplog.at_level("WARNING"):
        result = await fetch_json(
            url="https://example.com",
            params={},
            timeout=aiohttp.ClientTimeout(total=5),
            log_prefix="test",
            org_name="Acme",
        )

    assert result is None
    assert session.get_calls == 1
    assert "test_rate_limited" in caplog.text


async def test_post_json_array_accepts_201_and_returns_the_array(monkeypatch) -> None:
    session = FakeAiohttpSession(post=FakeAiohttpResponse(201, [{"a": 1}]))
    patch_aiohttp_session(monkeypatch, session)

    result = await post_json_array(
        url="https://example.com",
        params={"timeout": "10"},
        headers={"Authorization": "Bearer t"},
        body="{}",
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result == [{"a": 1}]
    assert session.post_calls[0][1]["headers"]["Content-Type"] == "application/json"


async def test_post_json_array_returns_none_for_a_non_array_body(monkeypatch) -> None:
    patch_aiohttp_session(
        monkeypatch, FakeAiohttpSession(post=FakeAiohttpResponse(200, {"error": "x"}))
    )

    result = await post_json_array(
        url="https://example.com",
        params={},
        headers={},
        body="{}",
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result is None
