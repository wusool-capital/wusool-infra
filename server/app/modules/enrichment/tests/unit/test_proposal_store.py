"""`InMemoryProposalStore` — a dict with TTL eviction, same shape as
`utilities.persistence.idempotency.InMemoryIdempotencyStore`.
"""

from app.modules.enrichment.api.slack.views.proposal_store import InMemoryProposalStore


def test_put_then_get_returns_the_same_payload() -> None:
    store = InMemoryProposalStore()
    token = store.put("some json")
    assert store.get(token) == "some json"


def test_put_returns_a_different_token_each_time() -> None:
    store = InMemoryProposalStore()
    assert store.put("a") != store.put("b")


def test_get_returns_none_for_an_unknown_token() -> None:
    store = InMemoryProposalStore()
    assert store.get("never-put") is None


def test_get_returns_none_after_ttl_expires() -> None:
    store = InMemoryProposalStore(ttl_seconds=-1.0)  # already expired the instant it's put
    token = store.put("some json")
    assert store.get(token) is None
