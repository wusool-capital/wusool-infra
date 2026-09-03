from app.modules.attio import WebhookEvent, WebhookEventId
from app.modules.ddl_commands.application import attio_sync as dispatch


def _event(event_type: str, **id_kwargs) -> WebhookEvent:
    return WebhookEvent(event_type=event_type, id=WebhookEventId(**id_kwargs))


class _FakeClient:
    """Never actually called — `dispatch_event`'s own routing is tested here
    in isolation, with `_FakeRegistry`/`_FakeUpsert` standing in for the real
    `AttioRegistryPort`/`AttioSyncRepositoryPort` implementations (covered by
    their own tests / integration tests against a real database)."""

    async def get(self, path: str) -> dict:
        raise AssertionError("not used by this test")

    async def post(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")


class _FakeRegistry:
    """Maps the fixed object/list UUIDs this test suite uses to their slugs —
    a pure lookup, no Attio API call, since `dispatch_event` only ever calls
    this through the `AttioRegistryPort` interface."""

    _OBJECTS = {
        "org-object-uuid": "organizations",
        "person-object-uuid": "person",
        "deals-object-uuid": "deals",
        "deal-object-uuid": "deal",
        "note-object-uuid": "note",
        "tasks-object-uuid": "tasks",  # a real, known slug outside this sync's scope
    }
    _LISTS = {
        "buyer-role-list-uuid": "buyer_role",
        "seller-role-list-uuid": "seller_role",
        "mandates-list-uuid": "mandates",
    }

    async def object_slug(self, client, object_id: str) -> str | None:
        return self._OBJECTS.get(object_id)

    async def list_slug(self, client, list_id: str) -> str | None:
        return self._LISTS.get(list_id)


class _FakeUpsert:
    """Records every sync/delete call `dispatch_event` makes through the
    `AttioSyncRepositoryPort` interface."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, str]] = []

    async def sync_organization(self, client, record_id: str) -> None:
        self.calls.append(("sync_organization", record_id))

    async def sync_person(self, client, record_id: str) -> None:
        self.calls.append(("sync_person", record_id))

    async def sync_deal(self, client, record_id: str, *, object_slug: str = "deals") -> None:
        self.calls.append((f"sync_deal[{object_slug}]", record_id))

    async def sync_note(self, client, record_id: str) -> None:
        self.calls.append(("sync_note", record_id))

    async def sync_buyer_role(self, client, entry_id: str) -> None:
        self.calls.append(("sync_buyer_role", entry_id))

    async def sync_seller_role(self, client, entry_id: str) -> None:
        self.calls.append(("sync_seller_role", entry_id))

    async def delete_organization(self, record_id: str) -> None:
        self.calls.append(("delete_organization", record_id))

    async def delete_person(self, record_id: str) -> None:
        self.calls.append(("delete_person", record_id))


async def test_record_created_dispatches_to_matching_sync_fn() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.created", object_id="org-object-uuid", record_id="org-1"),
    )

    assert upsert.calls == [("sync_organization", "org-1")]


async def test_source_deal_record_dispatches_to_matching_sync_fn() -> None:
    """SOURCE Attio's custom deal object (slug "deal", singular) must route
    just like DEV's native "deals" object — see `config.py`'s
    `attio_deal_object_slug`."""
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.created", object_id="deal-object-uuid", record_id="deal-1"),
    )

    assert upsert.calls == [("sync_deal[deal]", "deal-1")]


async def test_note_record_dispatches_to_matching_sync_fn() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.created", object_id="note-object-uuid", record_id="note-1"),
    )

    assert upsert.calls == [("sync_note", "note-1")]


async def test_record_deleted_dispatches_to_delete_fn() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.deleted", object_id="org-object-uuid", record_id="org-1"),
    )

    assert upsert.calls == [("delete_organization", "org-1")]


async def test_person_record_deleted_dispatches_to_delete_fn() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.deleted", object_id="person-object-uuid", record_id="person-1"),
    )

    assert upsert.calls == [("delete_person", "person-1")]


async def test_record_deleted_for_table_without_delete_handling_is_a_noop() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.deleted", object_id="deals-object-uuid", record_id="deal-1"),
    )

    assert upsert.calls == []  # sync_fn must not run for a deleted record


async def test_unknown_object_is_ignored() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("record.created", object_id="tasks-object-uuid", record_id="task-1"),
    )

    assert upsert.calls == []


async def test_list_entry_created_dispatches_to_matching_sync_fn() -> None:
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("list-entry.created", list_id="buyer-role-list-uuid", entry_id="entry-1"),
    )

    assert upsert.calls == [("sync_buyer_role", "entry-1")]


async def test_list_entry_deleted_is_a_noop() -> None:
    """No table's list-entry deletion is handled yet — see `upsert.py`'s
    module docstring for why this mirrors sync-postgres.ps1's existing gap
    rather than introducing a new one."""
    upsert = _FakeUpsert()

    await dispatch.dispatch_event(
        upsert,
        _FakeRegistry(),
        _FakeClient(),
        _event("list-entry.deleted", list_id="buyer-role-list-uuid", entry_id="entry-1"),
    )

    assert upsert.calls == []


async def test_unrecognized_event_type_is_ignored() -> None:
    upsert = _FakeUpsert()
    await dispatch.dispatch_event(upsert, _FakeRegistry(), _FakeClient(), _event("webhook.test"))
    assert upsert.calls == []


async def test_missing_ids_are_ignored() -> None:
    upsert = _FakeUpsert()
    await dispatch.dispatch_event(upsert, _FakeRegistry(), _FakeClient(), _event("record.created"))
    assert upsert.calls == []
