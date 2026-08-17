import pytest

from ddl_commands.modules.attio_sync import dispatch, registry


class _FakeClient:
    """Only serves `/objects` and `/lists` — dispatch's own routing is
    tested here in isolation from the per-table sync functions, which are
    monkeypatched out (they're covered by their own tests / integration
    tests against a real database)."""

    async def get(self, path: str) -> dict:
        if path == "/objects":
            return {
                "data": [
                    {"id": {"object_id": "org-object-uuid"}, "api_slug": "organizations"},
                    {"id": {"object_id": "person-object-uuid"}, "api_slug": "person"},
                    {"id": {"object_id": "deals-object-uuid"}, "api_slug": "deals"},
                    {"id": {"object_id": "tasks-object-uuid"}, "api_slug": "tasks"},
                ]
            }
        if path == "/lists":
            return {
                "data": [
                    {"id": {"list_id": "buyer-role-list-uuid"}, "api_slug": "buyer_role"},
                    {"id": {"list_id": "seller-role-list-uuid"}, "api_slug": "seller_role"},
                    {"id": {"list_id": "mandates-list-uuid"}, "api_slug": "mandates"},
                ]
            }
        raise AssertionError(f"unexpected path {path}")


@pytest.fixture(autouse=True)
def _reset_registry_cache():
    registry.reset_cache()
    yield
    registry.reset_cache()


def _async_recorder(calls: list, arity: int):
    """Returns an awaitable stand-in for a sync/delete fn that just records
    its last positional argument — dispatch.py always awaits these."""

    if arity == 1:

        async def record_one(arg) -> None:
            calls.append(arg)

        return record_one

    async def record_two(_client, arg) -> None:
        calls.append(arg)

    return record_two


async def test_record_created_dispatches_to_matching_sync_fn(monkeypatch) -> None:
    calls = []
    monkeypatch.setitem(dispatch._OBJECT_SYNC, "organizations", _async_recorder(calls, arity=2))

    await dispatch.dispatch_event(
        _FakeClient(),
        {
            "event_type": "record.created",
            "id": {"object_id": "org-object-uuid", "record_id": "org-1"},
        },
    )

    assert calls == ["org-1"]


async def test_record_deleted_dispatches_to_delete_fn(monkeypatch) -> None:
    calls = []
    monkeypatch.setitem(dispatch._OBJECT_DELETE, "organizations", _async_recorder(calls, arity=1))

    await dispatch.dispatch_event(
        _FakeClient(),
        {
            "event_type": "record.deleted",
            "id": {"object_id": "org-object-uuid", "record_id": "org-1"},
        },
    )

    assert calls == ["org-1"]


async def test_record_deleted_for_table_without_delete_handling_is_a_noop(monkeypatch) -> None:
    calls = []
    monkeypatch.setitem(dispatch._OBJECT_SYNC, "person", _async_recorder(calls, arity=2))

    await dispatch.dispatch_event(
        _FakeClient(),
        {
            "event_type": "record.deleted",
            "id": {"object_id": "person-object-uuid", "record_id": "person-1"},
        },
    )

    assert calls == []  # sync_fn must not run for a deleted record


async def test_unknown_object_is_ignored(monkeypatch) -> None:
    calls = []
    monkeypatch.setattr(
        dispatch, "_OBJECT_SYNC", {"organizations": _async_recorder(calls, arity=2)}
    )

    await dispatch.dispatch_event(
        _FakeClient(),
        {
            "event_type": "record.created",
            "id": {"object_id": "tasks-object-uuid", "record_id": "task-1"},
        },
    )

    assert calls == []


async def test_list_entry_created_dispatches_to_matching_sync_fn(monkeypatch) -> None:
    calls = []
    monkeypatch.setitem(dispatch._LIST_SYNC, "buyer_role", _async_recorder(calls, arity=2))

    await dispatch.dispatch_event(
        _FakeClient(),
        {
            "event_type": "list-entry.created",
            "id": {"list_id": "buyer-role-list-uuid", "entry_id": "entry-1"},
        },
    )

    assert calls == ["entry-1"]


async def test_list_entry_deleted_is_a_noop() -> None:
    """No table's list-entry deletion is handled yet — see upsert.py's
    module docstring for why this mirrors sync-postgres.ps1's existing gap
    rather than introducing a new one."""
    # Should not raise even though no delete handler is registered for lists.
    await dispatch.dispatch_event(
        _FakeClient(),
        {
            "event_type": "list-entry.deleted",
            "id": {"list_id": "buyer-role-list-uuid", "entry_id": "entry-1"},
        },
    )


async def test_unrecognized_event_type_is_ignored() -> None:
    await dispatch.dispatch_event(_FakeClient(), {"event_type": "webhook.test", "id": {}})


async def test_missing_ids_are_ignored() -> None:
    await dispatch.dispatch_event(_FakeClient(), {"event_type": "record.created", "id": {}})
