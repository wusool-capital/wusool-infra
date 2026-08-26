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
    def __init__(self, api_key: str) -> None:
        self._headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }

    async def get(self, path: str) -> dict:
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.get(f"{_BASE_URL}{path}") as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise AttioError(resp.status, body)
                return await resp.json()

    async def post(self, path: str, json_body: dict) -> dict:
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.post(f"{_BASE_URL}{path}", json=json_body) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise AttioError(resp.status, body)
                return await resp.json()

    async def patch(self, path: str, json_body: dict) -> dict:
        async with aiohttp.ClientSession(headers=self._headers) as session:
            async with session.patch(f"{_BASE_URL}{path}", json=json_body) as resp:
                body = await resp.text()
                if resp.status >= 400:
                    raise AttioError(resp.status, body)
                return await resp.json()


@lru_cache
def get_attio_client() -> AttioClient:
    return AttioClient(get_settings().attio_api_key)
