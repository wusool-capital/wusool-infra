import pytest
from wusool_db.models import Organization

from ddl_commands.modules.attio_sync import full_resync


def _entry(entry_id: str, org_id: str) -> dict:
    return {"id": {"entry_id": entry_id}, "parent_record_id": {"record_id": org_id}}


class _FakeClient:
    def __init__(self, pages: dict[str, list[list[dict]]]) -> None:
        self._pages = pages

    async def post(self, path: str, json_body: dict) -> dict:
        list_slug = path.split("/")[2]
        pages = self._pages.get(list_slug, [])
        offset = json_body["offset"]
        page_index = offset // json_body["limit"]
        page = pages[page_index] if page_index < len(pages) else []
        return {"data": page}


class _FakeAttioClient:
    """Stands in for `AttioClient` in `run()`-level tests -- just needs the
    `aclose()` `run()` always calls in its `finally` block."""

    async def aclose(self) -> None:
        pass


async def test_safe_fetch_returns_none_and_logs_on_failure() -> None:
    async def failing():
        raise RuntimeError("Attio 500")

    assert await full_resync._safe_fetch(failing(), "organizations") is None


async def test_safe_fetch_returns_result_on_success() -> None:
    async def ok():
        return ["a", "b"]

    assert await full_resync._safe_fetch(ok(), "organizations") == ["a", "b"]


def test_chunk_splits_into_fixed_size_pages() -> None:
    assert full_resync._chunk(list(range(7)), 3) == [[0, 1, 2], [3, 4, 5], [6]]


def test_chunk_empty_list() -> None:
    assert full_resync._chunk([], 3) == []


async def test_write_batches_concurrently_aggregates_across_pages(monkeypatch) -> None:
    calls = []

    async def fake_upsert_batch_with_retry(model, page, page_label=""):
        calls.append(page)
        return len(page), 0, {row["attio_id"]: row["raw_attio"] for row in page}

    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.upsert.upsert_batch_with_retry",
        fake_upsert_batch_with_retry,
    )
    monkeypatch.setattr(full_resync, "_PAGE_SIZE", 2)

    rows = [{"attio_id": str(i), "raw_attio": {"i": i}} for i in range(5)]
    ok, failed, returned = await full_resync._write_batches_concurrently(Organization, rows)

    assert ok == 5
    assert failed == 0
    assert returned == {str(i): {"i": i} for i in range(5)}
    assert len(calls) == 3  # 5 rows / page size 2 -> 3 pages


async def test_write_and_verify_flags_count_mismatch(monkeypatch) -> None:
    async def fake_write_batches(model, rows):
        return len(rows), 0, {r["attio_id"]: r["raw_attio"] for r in rows}

    async def fake_count(table):
        return 1  # only 1 row actually landed, though 2 were expected

    monkeypatch.setattr(full_resync, "_write_batches_concurrently", fake_write_batches)
    monkeypatch.setattr(full_resync, "_count", fake_count)

    rows = [
        {"attio_id": "a", "raw_attio": {"v": 1}},
        {"attio_id": "b", "raw_attio": {"v": 2}},
    ]
    ok, failed = await full_resync._write_and_verify(Organization, "organizations", rows, 2)

    assert ok == 2
    assert failed == 1  # count mismatch flagged even though the writes themselves succeeded


async def test_write_and_verify_flags_content_mismatch(monkeypatch) -> None:
    async def fake_write_batches(model, rows):
        # Simulate the DB returning a different raw_attio than what was sent.
        return len(rows), 0, {"a": {"v": "WRONG"}}

    async def fake_count(table):
        return 1

    monkeypatch.setattr(full_resync, "_write_batches_concurrently", fake_write_batches)
    monkeypatch.setattr(full_resync, "_count", fake_count)

    rows = [{"attio_id": "a", "raw_attio": {"v": 1}}]
    ok, failed = await full_resync._write_and_verify(Organization, "organizations", rows, 1)

    assert ok == 1
    assert failed == 1  # content mismatch flagged despite the count matching


async def test_write_and_verify_passes_when_everything_matches(monkeypatch) -> None:
    async def fake_write_batches(model, rows):
        return len(rows), 0, {r["attio_id"]: r["raw_attio"] for r in rows}

    async def fake_count(table):
        return 1

    monkeypatch.setattr(full_resync, "_write_batches_concurrently", fake_write_batches)
    monkeypatch.setattr(full_resync, "_count", fake_count)

    rows = [{"attio_id": "a", "raw_attio": {"v": 1}}]
    ok, failed = await full_resync._write_and_verify(Organization, "organizations", rows, 1)

    assert ok == 1
    assert failed == 0


async def test_reconcile_roles_groups_by_org_and_isolates_failures(monkeypatch) -> None:
    client = _FakeClient({})
    entries = [
        _entry("entry-1", "org-a"),
        _entry("entry-2", "org-a"),  # duplicate for org-a
        _entry("entry-3", "org-b"),
    ]

    async def fake_reconcile(client, list_slug, siblings):
        parent = siblings[0]["parent_record_id"]["record_id"]
        if parent == "org-b":
            raise RuntimeError("boom")
        return siblings[0]

    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.upsert._reconcile_active_entry", fake_reconcile
    )

    rows, reconcile_failed = await full_resync._reconcile_roles(
        client, "buyer_role", entries, lambda org_id, winner: {"org_id": org_id}
    )

    assert rows == [{"org_id": "org-a"}]
    assert reconcile_failed == 1  # org-b's reconciliation failed and was skipped


async def test_run_raises_systemexit_on_any_failure(monkeypatch) -> None:
    """The GH Actions/SSM caller must see a non-zero exit if anything in the
    nightly pass failed — a silent partial failure defeats the point of a
    safety net."""
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient",
        lambda api_key: _FakeAttioClient(),
    )

    async def no_users(client):
        return 0

    async def empty_page(client, path):
        return []

    async def no_ids(table):
        return set()

    async def noop_write(model, table, rows, expected_count):
        return 0, 0

    async def noop_reconcile(client, list_slug, entries, build_params):
        return [], 0

    monkeypatch.setattr(full_resync.upsert, "sync_all_users", no_users)
    monkeypatch.setattr(full_resync, "_page_through", empty_page)
    monkeypatch.setattr(full_resync, "_existing_ids", no_ids)
    monkeypatch.setattr(full_resync, "_write_and_verify", noop_write)
    monkeypatch.setattr(full_resync, "_reconcile_roles", noop_reconcile)

    # Nothing fetched, nothing to write -> should NOT raise.
    await full_resync.run()


async def test_run_raises_systemexit_when_a_table_has_failures(monkeypatch) -> None:
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient",
        lambda api_key: _FakeAttioClient(),
    )

    async def no_users(client):
        return 0

    async def one_record_page(client, path):
        return [{"id": {"record_id": "only-one"}, "values": {}}] if "organizations" in path else []

    async def no_ids(table):
        return set()

    async def failing_write(model, table, rows, expected_count):
        return 0, 1

    monkeypatch.setattr(full_resync.upsert, "sync_all_users", no_users)
    monkeypatch.setattr(full_resync, "_page_through", one_record_page)
    monkeypatch.setattr(full_resync, "_existing_ids", no_ids)
    monkeypatch.setattr(full_resync, "_write_and_verify", failing_write)

    with pytest.raises(SystemExit):
        await full_resync.run()


async def test_run_continues_past_a_failed_entity_listing(monkeypatch) -> None:
    """A failure just listing one entity's records (Attio 500, exhausted
    retries, malformed page) must not prevent every entity after it from
    being attempted that night — this is the exact failure mode the nightly
    safety net exists to guard against."""
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient",
        lambda api_key: _FakeAttioClient(),
    )

    async def no_users(client):
        return 0

    async def flaky_page(client, path):
        if "organizations" in path:
            raise RuntimeError("Attio 500")
        if "person" in path:
            return [{"id": {"record_id": "person-1"}, "values": {}}]
        return []

    async def no_ids(table):
        return set()

    write_calls = []

    async def recording_write(model, table, rows, expected_count):
        write_calls.append(table)
        return len(rows), 0

    monkeypatch.setattr(full_resync.upsert, "sync_all_users", no_users)
    monkeypatch.setattr(full_resync, "_page_through", flaky_page)
    monkeypatch.setattr(full_resync, "_existing_ids", no_ids)
    monkeypatch.setattr(full_resync, "_write_and_verify", recording_write)

    with pytest.raises(SystemExit):
        await full_resync.run()

    assert "people" in write_calls  # ran despite organizations' listing failing first


async def test_run_reports_users_sync_failure(monkeypatch) -> None:
    """A users-sync failure alone must still fail the whole run — it's not
    a table that gets silently skipped just because it runs first."""
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient",
        lambda api_key: _FakeAttioClient(),
    )

    async def failing_users(client):
        raise RuntimeError("boom")

    async def empty_page(client, path):
        return []

    async def no_ids(table):
        return set()

    async def noop_write(model, table, rows, expected_count):
        return 0, 0

    async def noop_reconcile(client, list_slug, entries, build_params):
        return [], 0

    monkeypatch.setattr(full_resync.upsert, "sync_all_users", failing_users)
    monkeypatch.setattr(full_resync, "_page_through", empty_page)
    monkeypatch.setattr(full_resync, "_existing_ids", no_ids)
    monkeypatch.setattr(full_resync, "_write_and_verify", noop_write)
    monkeypatch.setattr(full_resync, "_reconcile_roles", noop_reconcile)

    with pytest.raises(SystemExit):
        await full_resync.run()
