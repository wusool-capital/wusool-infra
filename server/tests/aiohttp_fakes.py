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

import aiohttp


class FakeAiohttpResponse:
    def __init__(self, status: int, body: dict) -> None:
        self.status = status
        self._body = body

    async def json(self) -> dict:
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
        get: "FakeAiohttpResponse | Exception | None" = None,
        post: "FakeAiohttpResponse | Exception | None" = None,
    ) -> None:
        self._get = get
        self._post = post

    def get(self, url: str, **kwargs: object) -> FakeAiohttpResponse:
        return self._resolve(self._get, "get")

    def post(self, url: str, **kwargs: object) -> FakeAiohttpResponse:
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
    monkeypatch.setattr(aiohttp, "ClientSession", lambda **kwargs: session)  # noqa: ARG005
