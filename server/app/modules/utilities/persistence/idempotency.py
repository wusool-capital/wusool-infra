"""Concrete `IdempotencyStore` implementation."""

import time

from app.modules.utilities.application.ports.idempotency import IdempotencyStore

__all__ = ["IdempotencyStore", "InMemoryIdempotencyStore"]


class InMemoryIdempotencyStore:
    """A dict with TTL eviction. Fine for a single process at this scale;
    isolated behind `IdempotencyStore` so it can move to Redis/a database
    table later without the Slack handler changing.
    """

    def __init__(self, ttl_seconds: float = 300.0) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, float] = {}

    def seen(self, key: str) -> bool:
        self._evict_expired()
        return key in self._entries

    def mark(self, key: str) -> None:
        self._entries[key] = time.monotonic()

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            k for k, marked_at in self._entries.items() if now - marked_at > self._ttl_seconds
        ]
        for key in expired:
            del self._entries[key]
