"""The prod half of the sync must never ingest a dev record.

One SOURCE Attio workspace now serves both environments, so a dev
`/add-seller` fires a webhook that reaches the *production* endpoint. These
tests pin the one behaviour that stops dev test data landing in the
production database — stated once per entity, with no database involved: an
out-of-scope record must not open a session at all.
"""

import pytest

from app.modules.attio.config import record_scope
from app.modules.attio.providers.attio import values as v
from app.modules.ddl_commands.persistence import attio_sync as upsert


def _values(is_test: bool | None) -> dict:
    if is_test is None:
        return {}
    return {"is_test": [{"active_until": None, "value": is_test}]}


def _record(is_test: bool | None) -> dict:
    return {"id": {"record_id": "rec-1"}, "values": _values(is_test)}


def _entry(is_test: bool | None, *, entry_id: str = "entry-1") -> dict:
    return {
        "id": {"entry_id": entry_id},
        "parent_record_id": {"record_id": "org-1"},
        "created_at": "2026-09-01T00:00:00Z",
        "entry_values": _values(is_test),
    }


class _FakeClient:
    """Serves one fetched record and records every call. `post` doubles as
    the list-entries query used by `_fetch_siblings`."""

    def __init__(self, fetched: dict) -> None:
        self._fetched = fetched
        self.get_calls: list[str] = []
        self.post_calls: list[str] = []

    async def get(self, path: str) -> dict:
        self.get_calls.append(path)
        return {"data": self._fetched}

    async def post(self, path: str, json_body: dict) -> dict:
        self.post_calls.append(path)
        return {"data": []}

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("an out-of-scope sync must never write back to Attio")


def _explode() -> object:
    raise AssertionError("an out-of-scope record must not open a database session")


# ---------------------------------------------------------------------------
# The null policy
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("raw", "belongs_to_test"),
    [
        (None, False),  # unset — the state of every record predating 2026-09-07
        (False, False),
        (True, True),
        ("true", True),  # Attio's own string shapes, via v.boolean
        ("checked", True),
    ],
)
def test_unset_is_test_reads_as_production(raw: object, belongs_to_test: bool) -> None:
    raw_values = {"is_test": [{"active_until": None, "value": raw}]}

    assert record_scope(v.boolean(raw_values, "is_test")) is belongs_to_test


def test_a_record_with_no_is_test_key_at_all_reads_as_production() -> None:
    assert record_scope(v.boolean(v.vals(_record(None)), "is_test")) is False


# ---------------------------------------------------------------------------
# One per single-record wrapper: no session, no write
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("sync_fn", "path_fragment"),
    [
        (upsert.sync_organization, "/objects/organizations/records/"),
        (upsert.sync_person, "/objects/person/records/"),
        (upsert.sync_deal, "/objects/deal/records/"),
        (upsert.sync_note, "/objects/note/records/"),
    ],
)
async def test_out_of_scope_record_is_not_written(monkeypatch, sync_fn, path_fragment) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", _explode)
    client = _FakeClient(_record(is_test=True))

    await sync_fn(client, "rec-1")

    assert client.get_calls == [f"{path_fragment}rec-1"]


@pytest.mark.parametrize("list_slug", ["buyer_role", "seller_role"])
async def test_out_of_scope_role_entry_is_not_written(monkeypatch, list_slug) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", _explode)
    sync_fn = getattr(upsert, f"sync_{list_slug}")
    client = _FakeClient(_entry(is_test=True))

    await sync_fn(client, "entry-1")

    assert client.get_calls == [f"/lists/{list_slug}/entries/entry-1"]


@pytest.mark.parametrize("list_slug", ["buyer_role", "seller_role"])
async def test_out_of_scope_role_entry_returns_before_fetching_siblings(
    monkeypatch, list_slug
) -> None:
    """`_reconcile_active_entry` PATCHes `is_active` back into Attio. If the
    scope check ran after `_fetch_siblings`, a production process would
    reconcile — and therefore write to — a dev entry. No `post` means no
    sibling query, so no reconciliation can have happened."""
    monkeypatch.setattr(upsert, "get_sessionmaker", _explode)
    sync_fn = getattr(upsert, f"sync_{list_slug}")
    client = _FakeClient(_entry(is_test=True))

    await sync_fn(client, "entry-1")

    assert client.post_calls == []


# ---------------------------------------------------------------------------
# The subtle one: reconciliation must not cross scopes
# ---------------------------------------------------------------------------


class _FakeResult:
    def scalar_one(self) -> str:
        return "row-1"


class _FakeSession:
    async def execute(self, *_args, **_kwargs) -> _FakeResult:
        return _FakeResult()

    async def commit(self) -> None:
        return None

    async def __aenter__(self) -> "_FakeSession":
        return self

    async def __aexit__(self, *_exc: object) -> None:
        return None


class _SiblingClient:
    """Returns `siblings` from the list-entries query and `trigger` from the
    single-entry GET, recording every PATCH."""

    def __init__(self, trigger: dict, siblings: list[dict]) -> None:
        self._trigger = trigger
        self._siblings = siblings
        self.patch_calls: list[str] = []

    async def get(self, path: str) -> dict:
        return {"data": self._trigger}

    async def post(self, path: str, json_body: dict) -> dict:
        return {"data": self._siblings if json_body.get("offset", 0) == 0 else []}

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patch_calls.append(path)
        return {}


async def test_a_newer_test_entry_never_deactivates_a_production_entry(monkeypatch) -> None:
    """`_reconcile_active_entry` picks a winner by `created_at` and PATCHes
    every loser to `is_active=False`. A dev creating a test seller_role on an
    org that already has a real one would otherwise demote the production
    entry in Attio — corrupting the flag `resolve_role_entry_id` and the
    matching engine both read."""
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: _FakeSession)

    production = _entry(False, entry_id="entry-prod") | {"created_at": "2026-01-01T00:00:00Z"}
    production["entry_values"]["is_active"] = [{"active_until": None, "value": True}]
    newer_test = _entry(True, entry_id="entry-test") | {"created_at": "2026-09-01T00:00:00Z"}

    client = _SiblingClient(production, [production, newer_test])
    await upsert.sync_seller_role(client, "entry-prod")

    assert not any("entry-prod" in path for path in client.patch_calls)
