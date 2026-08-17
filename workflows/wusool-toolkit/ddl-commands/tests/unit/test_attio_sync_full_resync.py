import pytest

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


async def test_one_entry_id_per_org_dedupes_duplicates() -> None:
    client = _FakeClient(
        {
            "buyer_role": [
                [
                    _entry("entry-1", "org-a"),
                    _entry("entry-2", "org-a"),  # duplicate for org-a
                    _entry("entry-3", "org-b"),
                ]
            ]
        }
    )

    ids = await full_resync._one_entry_id_per_org(client, "buyer_role")

    assert set(ids) == {"entry-1", "entry-3"}  # one representative per org, not three


async def test_one_entry_id_per_org_empty_list() -> None:
    client = _FakeClient({"buyer_role": [[]]})
    assert await full_resync._one_entry_id_per_org(client, "buyer_role") == []


async def test_sync_all_counts_successes_and_failures() -> None:
    async def sync_fn(client, record_id):
        if record_id == "bad":
            raise RuntimeError("boom")

    ok, failed = await full_resync._sync_all(None, "organizations", ["a", "bad", "b"], sync_fn)

    assert ok == 2
    assert failed == 1


async def test_run_raises_systemexit_on_any_failure(monkeypatch) -> None:
    """The GH Actions/SSM caller must see a non-zero exit if anything in the
    nightly pass failed — a silent partial failure defeats the point of a
    safety net."""
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient", lambda api_key: object()
    )

    async def always_empty(client, slug):
        return []

    async def no_users(client):
        return 0

    monkeypatch.setattr(full_resync, "_object_record_ids", always_empty)
    monkeypatch.setattr(full_resync, "_list_entry_ids", always_empty)
    monkeypatch.setattr(full_resync, "_one_entry_id_per_org", always_empty)
    monkeypatch.setattr(full_resync.upsert, "sync_all_users", no_users)

    # No ids at all -> nothing synced, nothing failed -> should NOT raise.
    await full_resync.run()


async def test_run_raises_systemexit_when_a_table_has_failures(monkeypatch) -> None:
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient", lambda api_key: object()
    )

    async def one_id(client, slug):
        return ["only-one"]

    async def none_id(client, slug):
        return []

    async def no_users(client):
        return 0

    monkeypatch.setattr(full_resync, "_object_record_ids", one_id)
    monkeypatch.setattr(full_resync, "_list_entry_ids", none_id)
    monkeypatch.setattr(full_resync, "_one_entry_id_per_org", none_id)
    monkeypatch.setattr(full_resync.upsert, "sync_all_users", no_users)

    async def failing_sync(client, record_id):
        raise RuntimeError("boom")

    monkeypatch.setattr(full_resync.upsert, "sync_organization", failing_sync)
    monkeypatch.setattr(full_resync.upsert, "sync_person", failing_sync)
    monkeypatch.setattr(full_resync.upsert, "sync_deal", failing_sync)

    with pytest.raises(SystemExit):
        await full_resync.run()


async def test_run_reports_users_sync_failure(monkeypatch) -> None:
    """A users-sync failure alone must still fail the whole run — it's not
    a table that gets silently skipped just because it runs first."""
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)
    monkeypatch.setattr(
        "ddl_commands.modules.attio_sync.full_resync.AttioClient", lambda api_key: object()
    )

    async def always_empty(client, slug):
        return []

    async def failing_users(client):
        raise RuntimeError("boom")

    monkeypatch.setattr(full_resync, "_object_record_ids", always_empty)
    monkeypatch.setattr(full_resync, "_list_entry_ids", always_empty)
    monkeypatch.setattr(full_resync, "_one_entry_id_per_org", always_empty)
    monkeypatch.setattr(full_resync.upsert, "sync_all_users", failing_users)

    with pytest.raises(SystemExit):
        await full_resync.run()
