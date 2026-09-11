"""Coverage for `fetch_json` — the fail-soft GET helper shared by Diffbot
and People Data Labs, extracted out of both clients since it was
byte-identical control flow. No real network call: `aiohttp.ClientSession`
is monkeypatched.
"""

import aiohttp

from app.modules.enrichment.providers.http_json import fetch_json


class _FakeResponse:
    def __init__(self, status: int, body: dict | None) -> None:
        self.status = status
        self._body = body

    async def json(self) -> dict:
        return self._body or {}

    async def __aenter__(self) -> "_FakeResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class _FakeSession:
    def __init__(self, response: _FakeResponse | Exception) -> None:
        self._response = response

    def get(self, url: str, params: dict) -> _FakeResponse:
        if isinstance(self._response, Exception):
            raise self._response
        return self._response

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


def _patch_session(monkeypatch, response: _FakeResponse | Exception) -> None:
    monkeypatch.setattr(
        aiohttp,
        "ClientSession",
        lambda **kwargs: _FakeSession(response),  # noqa: ARG005
    )


async def test_fetch_json_returns_body_on_200(monkeypatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(200, {"hello": "world"}))

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result == {"hello": "world"}


async def test_fetch_json_returns_none_on_non_200(monkeypatch) -> None:
    _patch_session(monkeypatch, _FakeResponse(500, None))

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result is None


async def test_fetch_json_returns_none_on_connection_error(monkeypatch) -> None:
    _patch_session(monkeypatch, ConnectionError("boom"))

    result = await fetch_json(
        url="https://example.com",
        params={},
        timeout=aiohttp.ClientTimeout(total=5),
        log_prefix="test",
        org_name="Acme",
    )

    assert result is None
