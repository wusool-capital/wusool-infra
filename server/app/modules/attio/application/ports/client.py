"""The Attio-calling surface every consumer depends on — implemented by
`providers/attio/client.py`'s `AttioClient`. Structural (duck-typed), so
tests can substitute a fake/stub client without subclassing the real one.
"""

from typing import Protocol


class AttioClientProtocol(Protocol):
    async def get(self, path: str) -> dict: ...
    async def post(self, path: str, json_body: dict) -> dict: ...
    async def patch(self, path: str, json_body: dict) -> dict: ...
