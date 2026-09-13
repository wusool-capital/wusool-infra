"""In-memory, TTL-evicted store for a proposal's encoded JSON — it no
longer fits directly in the "Review & Save" button's own `value` field
(Slack's `ButtonElement.value_max_length` hard-caps that at 2000
characters), now that `enrichment` proposes 20+ fields per target
(`field_plans.SELLER_ENRICHABLE_FIELDS`/`BUYER_ENRICHABLE_FIELDS`) rather
than the ~9 it shipped with — a well-documented company (confirmed live:
`/enrich-buyer Stripe`) routinely produces a JSON payload past that limit
on its own. The button now carries only an opaque token; `proposal_message
.decode_proposal` resolves it back via this store.

Same "one process, TTL dict" reasoning as
`utilities.persistence.idempotency.InMemoryIdempotencyStore`: this bot runs
one process per instance, and the payload only needs to survive the time
between the proposal message being posted and its button being clicked —
kept generous (not the idempotency store's 5 minutes) since a proposal can
sit unaddressed in a channel for a while before an operator gets to it.
"""

import time
import uuid
from functools import lru_cache

_DEFAULT_TTL_SECONDS = 24 * 60 * 60.0


class InMemoryProposalStore:
    def __init__(self, ttl_seconds: float = _DEFAULT_TTL_SECONDS) -> None:
        self._ttl_seconds = ttl_seconds
        self._entries: dict[str, tuple[str, float]] = {}

    def put(self, payload: str) -> str:
        """Returns a fresh opaque token — never the payload itself — safe
        to embed directly in a Slack button's `value`.
        """
        self._evict_expired()
        token = uuid.uuid4().hex
        self._entries[token] = (payload, time.monotonic())
        return token

    def get(self, token: str) -> str | None:
        """`None` for an unknown or expired token — the caller decides how
        to surface that (see `decode_proposal`), not this store.
        """
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
def get_shared_proposal_store() -> InMemoryProposalStore:
    """One process-wide store — `proposal_message.py`'s only consumer of
    this needs a single shared instance, the same way
    `get_shared_idempotency_store` is shared across every caller of it.
    """
    return InMemoryProposalStore()
