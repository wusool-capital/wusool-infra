"""Concrete `EphemeralStore` implementation."""

import time
import uuid
from functools import lru_cache

from app.modules.utilities.application.ports.ephemeral_store import EphemeralStore

__all__ = ["EphemeralStore", "InMemoryEphemeralStore", "get_shared_ephemeral_store"]

# Generous relative to `InMemoryIdempotencyStore`'s 5 minutes: that store
# only needs to survive one redelivery window, this one needs to survive
# however long a Slack message/modal sits unaddressed before an operator
# gets to it — could plausibly be hours, not seconds.
_DEFAULT_TTL_SECONDS = 24 * 60 * 60.0


class InMemoryEphemeralStore:
    """A dict with TTL eviction. Fine for a single process at this scale,
    same reasoning as `InMemoryIdempotencyStore` — isolated behind
    `EphemeralStore` so it can move to Redis/a database table later without
    any caller changing.
    """

    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[str, float]] = {}

    def put(self, payload: str) -> str:
        self._evict_expired()
        token = uuid.uuid4().hex
        self._entries[token] = (payload, time.monotonic())
        return token

    def get(self, token: str) -> str | None:
        self._evict_expired()
        entry = self._entries.get(token)
        return entry[0] if entry is not None else None

    def _evict_expired(self) -> None:
        now = time.monotonic()
        expired = [
            token
            for token, (_, stored_at) in self._entries.items()
            if now - stored_at > self._ttl_seconds
        ]
        for token in expired:
            del self._entries[token]


@lru_cache
def get_shared_ephemeral_store() -> InMemoryEphemeralStore:
    """One process-wide store shared by every caller — tokens are random
    UUIDs, not caller-chosen keys, so there is no collision risk in sharing
    one instance across modules (unlike `IdempotencyStore`, whose callers
    must themselves prefix keys).
    """
    return InMemoryEphemeralStore()
