"""Concrete `IdempotencyStore` implementation."""

import time
from functools import lru_cache

from app.modules.utilities.application.ports.idempotency import IdempotencyStore

__all__ = ["IdempotencyStore", "InMemoryIdempotencyStore", "get_shared_idempotency_store"]


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


@lru_cache
def get_shared_idempotency_store() -> InMemoryIdempotencyStore:
    """One process-wide store for every module's Slack idempotency checks —
    each handler module used to construct its own module-level
    `InMemoryIdempotencyStore()`, fragmenting the same kind of state across
    instances with no single place to tune the TTL. Every caller already
    prefixes its keys (e.g. `f"discovery:{run_id}"`), so sharing one
    instance across modules carries no collision risk.
    """
    return InMemoryIdempotencyStore()
