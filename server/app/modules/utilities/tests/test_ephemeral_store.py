"""`InMemoryEphemeralStore` — a dict with TTL eviction, used to keep a
growable payload out of a size-capped Slack field (button `value`, modal
`private_metadata`); only a short token round-trips through Slack itself.
"""

from app.modules.utilities.persistence.ephemeral_store import InMemoryEphemeralStore


def test_put_then_get_returns_the_same_payload() -> None:
    store = InMemoryEphemeralStore()
    token = store.put("some payload")
    assert store.get(token) == "some payload"


def test_put_returns_a_different_token_each_time() -> None:
    store = InMemoryEphemeralStore()
    assert store.put("a") != store.put("b")


def test_get_returns_none_for_an_unknown_token() -> None:
    store = InMemoryEphemeralStore()
    assert store.get("never-put") is None


def test_get_returns_none_after_ttl_expires() -> None:
    store = InMemoryEphemeralStore(ttl_seconds=-1.0)  # already expired the instant it's put
    token = store.put("some payload")
    assert store.get(token) is None
