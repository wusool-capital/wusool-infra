"""Slack-delivery idempotency, kept behind a Protocol so a durable store
(Redis, a database table) can replace the in-memory default later without
touching the Slack handler (§28).
"""

from app.shared.idempotency.store import IdempotencyStore, InMemoryIdempotencyStore

__all__ = ["IdempotencyStore", "InMemoryIdempotencyStore"]
