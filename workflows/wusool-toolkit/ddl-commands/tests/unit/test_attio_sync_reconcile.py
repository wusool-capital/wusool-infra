from ddl_commands.modules.attio_sync.upsert import (
    _fetch_siblings,
    _reconcile_active_entry,
    group_entries_by_org,
)


def _entry(entry_id: str, org_id: str, created_at: str, is_active: bool | None = None) -> dict:
    entry_values: dict = {}
    if is_active is not None:
        entry_values["is_active"] = [{"active_until": None, "value": is_active}]
    return {
        "id": {"entry_id": entry_id},
        "parent_record_id": {"record_id": org_id},
        "created_at": created_at,
        "entry_values": entry_values,
    }


class _FakeClient:
    def __init__(self, entry_pages: list[list[dict]]) -> None:
        self._entry_pages = entry_pages
        self.patch_calls: list[tuple[str, dict]] = []

    async def post(self, path: str, json_body: dict) -> dict:
        offset = json_body["offset"]
        page_index = offset // json_body["limit"]
        page = self._entry_pages[page_index] if page_index < len(self._entry_pages) else []
        return {"data": page}

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patch_calls.append((path, json_body))
        return {}


async def test_single_entry_with_missing_is_active_becomes_active() -> None:
    entry = _entry("entry-1", "org-a", "2024-01-01T00:00:00Z")
    client = _FakeClient([])

    reconciled = await _reconcile_active_entry(client, "buyer_role", [entry])

    assert reconciled[0]["id"]["entry_id"] == "entry-1"
    assert client.patch_calls == [
        ("/lists/buyer_role/entries/entry-1", {"data": {"entry_values": {"is_active": True}}})
    ]


async def test_single_entry_already_active_is_left_alone() -> None:
    entry = _entry("entry-1", "org-a", "2024-01-01T00:00:00Z", is_active=True)
    client = _FakeClient([])

    await _reconcile_active_entry(client, "buyer_role", [entry])

    assert client.patch_calls == []


async def test_newest_entry_wins_and_older_flips_to_inactive() -> None:
    older = _entry("entry-old", "org-a", "2024-01-01T00:00:00Z", is_active=True)
    newer = _entry("entry-new", "org-a", "2024-01-03T00:00:00Z", is_active=None)
    client = _FakeClient([])

    reconciled = await _reconcile_active_entry(client, "buyer_role", [older, newer])

    assert reconciled[0]["id"]["entry_id"] == "entry-new"
    assert (
        "/lists/buyer_role/entries/entry-new",
        {"data": {"entry_values": {"is_active": True}}},
    ) in client.patch_calls
    assert (
        "/lists/buyer_role/entries/entry-old",
        {"data": {"entry_values": {"is_active": False}}},
    ) in client.patch_calls
    assert len(client.patch_calls) == 2


async def test_already_converged_state_issues_no_patches() -> None:
    older = _entry("entry-old", "org-a", "2024-01-01T00:00:00Z", is_active=False)
    newer = _entry("entry-new", "org-a", "2024-01-03T00:00:00Z", is_active=True)
    client = _FakeClient([])

    await _reconcile_active_entry(client, "buyer_role", [older, newer])

    assert client.patch_calls == []


async def test_siblings_from_other_orgs_are_excluded() -> None:
    mine = _entry("entry-mine", "org-a", "2024-01-01T00:00:00Z")
    other = _entry("entry-other", "org-b", "2024-01-02T00:00:00Z")
    client = _FakeClient([[mine, other]])

    siblings = await _fetch_siblings(client, "buyer_role", "org-a")

    assert [s["id"]["entry_id"] for s in siblings] == ["entry-mine"]


async def test_fetch_siblings_pages_through_multiple_pages() -> None:
    page_1 = [_entry(f"filler-{i}", "org-other", "2024-01-01T00:00:00Z") for i in range(500)]
    page_2 = [_entry("entry-target", "org-target", "2024-01-02T00:00:00Z")]
    client = _FakeClient([page_1, page_2])

    siblings = await _fetch_siblings(client, "buyer_role", "org-target")

    assert [s["id"]["entry_id"] for s in siblings] == ["entry-target"]


def test_group_entries_by_org_groups_duplicates_and_keeps_others_separate() -> None:
    mine_1 = _entry("entry-mine-1", "org-a", "2024-01-01T00:00:00Z")
    mine_2 = _entry("entry-mine-2", "org-a", "2024-01-02T00:00:00Z")
    other = _entry("entry-other", "org-b", "2024-01-01T00:00:00Z")

    by_org = group_entries_by_org([mine_1, mine_2, other])

    assert {e["id"]["entry_id"] for e in by_org["org-a"]} == {"entry-mine-1", "entry-mine-2"}
    assert [e["id"]["entry_id"] for e in by_org["org-b"]] == ["entry-other"]
