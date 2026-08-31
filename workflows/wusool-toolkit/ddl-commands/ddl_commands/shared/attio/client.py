"""Thin async wrapper over DEV Attio's REST API (`https://api.attio.com/v2`).
No retries, no rate-limit handling — this is a synchronous, human-triggered
write inside a single Slack interaction, not a batch job; a failure here
should surface immediately, not be silently retried.
"""

from functools import lru_cache

import aiohttp

from ddl_commands.config import get_settings

_BASE_URL = "https://api.attio.com/v2"


class AttioError(Exception):
    """Raised for any non-2xx response from the Attio API."""

    def __init__(self, status: int, body: str) -> None:
        self.status = status
        self.body = body
        super().__init__(f"Attio API error {status}: {body}")


class AttioClient:
    """Reuses one `aiohttp.ClientSession` across every call instead of
    opening a new TCP+TLS connection per request — matters most for
    `full_resync.py`, which can make thousands of calls in one run. The
    long-lived server singleton (`get_attio_client()`) just keeps its
    session for the process's lifetime; short-lived callers should use this
    as `async with AttioClient(...) as client:` (or call `aclose()`
    explicitly) so the session gets cleaned up on exit.
    """

    def __init__(self, api_key: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        self._session: aiohttp.ClientSession | None = None

    async def _get_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(headers=self._headers)
        return self._session

    async def aclose(self) -> None:
        if self._session is not None and not self._session.closed:
            await self._session.close()

    async def __aenter__(self) -> "AttioClient":
        return self

    async def __aexit__(self, *exc_info: object) -> None:
        await self.aclose()

    async def get(self, path: str) -> dict:
        session = await self._get_session()
        async with session.get(f"{_BASE_URL}{path}") as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise AttioError(resp.status, body)
            return await resp.json()

    async def post(self, path: str, json_body: dict) -> dict:
        session = await self._get_session()
        async with session.post(f"{_BASE_URL}{path}", json=json_body) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise AttioError(resp.status, body)
            return await resp.json()

    async def patch(self, path: str, json_body: dict) -> dict:
        session = await self._get_session()
        async with session.patch(f"{_BASE_URL}{path}", json=json_body) as resp:
            body = await resp.text()
            if resp.status >= 400:
                raise AttioError(resp.status, body)
            return await resp.json()


@lru_cache
def get_attio_client() -> AttioClient:
    return AttioClient(get_settings().attio_api_key)
