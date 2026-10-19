"""Shared fake for tests that monkeypatch `aiohttp.ClientSession` directly
rather than mocking an SDK object — every provider that talks to a vendor
via raw `aiohttp` instead of an SDK client.

Previously near-identical private copies in `enrichment`'s and `discovery`'s
own provider test suites (one GET-only, one GET+POST) — sharing test-tree
code carries none of production code's cross-module import restrictions
(see `test_architecture.py`'s own `_module_source_files`, which excludes
any path with `tests` in it; `slack_test_helpers.py`'s own docstring
already established the same precedent for Slack dispatch tests).
"""

from dataclasses import dataclass, field

import aiohttp
from pydantic import JsonValue

JsonBody = dict[str, JsonValue] | list[JsonValue]


@dataclass(frozen=True)
class RecordedRequest:
    """One request the code under test made, for asserting on afterwards."""

    url: str
    params: dict[str, str] = field(default_factory=dict)
    headers: dict[str, str] = field(default_factory=dict)
    data: str | None = None


class FakeAiohttpResponse:
    def __init__(self, status: int, body: JsonBody, headers: dict[str, str] | None = None) -> None:
        self.status = status
        self._body = body
        self.headers = headers or {}

    async def json(self) -> JsonBody:
        return self._body

    async def __aenter__(self) -> "FakeAiohttpResponse":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


class FakeAiohttpSession:
    """Routes `get`/`post` to separately scripted responses (or
    exceptions), keyed by verb — a caller exercising only one verb (e.g.
    `enrichment`'s GET-only `fetch_json`) just leaves the other unset.
    """

    def __init__(
        self,
        *,
        get: "FakeAiohttpResponse | Exception | list[FakeAiohttpResponse] | None" = None,
        post: "FakeAiohttpResponse | Exception | None" = None,
    ) -> None:
        self._get = get
        self._post = post
        self.get_calls = 0
        self.post_calls: list[RecordedRequest] = []
        self.timeouts: list[aiohttp.ClientTimeout | None] = []

    def get(self, url: str, **kwargs: object) -> FakeAiohttpResponse:
        self.get_calls += 1
        # A list scripts consecutive calls in order (the last one repeats).
        if isinstance(self._get, list):
            return self._get.pop(0) if len(self._get) > 1 else self._get[0]
        return self._resolve(self._get, "get")

    def post(
        self,
        url: str,
        *,
        params: dict[str, str] | None = None,
        headers: dict[str, str] | None = None,
        data: str | None = None,
        json: dict[str, JsonValue] | None = None,
    ) -> FakeAiohttpResponse:
        self.post_calls.append(
            RecordedRequest(url=url, params=params or {}, headers=headers or {}, data=data)
        )
        return self._resolve(self._post, "post")

    @staticmethod
    def _resolve(
        response: "FakeAiohttpResponse | Exception | None", verb: str
    ) -> FakeAiohttpResponse:
        if isinstance(response, Exception):
            raise response
        assert response is not None, f"no {verb} response scripted"
        return response

    async def __aenter__(self) -> "FakeAiohttpSession":
        return self

    async def __aexit__(self, *args: object) -> None:
        return None


def patch_aiohttp_session(monkeypatch, session: FakeAiohttpSession) -> None:
    def _client_session(*, timeout: aiohttp.ClientTimeout | None = None) -> FakeAiohttpSession:
        session.timeouts.append(timeout)
        return session

    monkeypatch.setattr(aiohttp, "ClientSession", _client_session)
