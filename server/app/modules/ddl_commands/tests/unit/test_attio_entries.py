import pytest

from app.modules.attio.providers.attio.entries import (
    RoleEntryNotFoundError,
    ScopeMismatchError,
    assert_organization_in_scope,
    create_organization,
    create_person,
    create_role_entry,
    find_people_by_email,
    patch_organization,
    patch_person,
    patch_role_entry,
    resolve_role_entry_id,
)


class _FakeClient:
    def __init__(self, entry_pages: list[list[dict]] | None = None) -> None:
        self._entry_pages = entry_pages or []
        self.post_calls: list[tuple[str, dict]] = []
        self.patch_calls: list[tuple[str, dict]] = []

    async def post(self, path: str, json_body: dict) -> dict:
        self.post_calls.append((path, json_body))
        offset = json_body["offset"]
        page_index = offset // json_body["limit"]
        page = self._entry_pages[page_index] if page_index < len(self._entry_pages) else []
        return {"data": page}

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patch_calls.append((path, json_body))
        return {}

    async def get(self, path: str) -> dict:
        raise AssertionError("not used by this test")


def _entry(
    entry_id: str,
    parent_record_id: str,
    *,
    is_active: bool | None = None,
    is_test: bool | None = None,
    created_at: str = "",
    target_vertical: str | None = None,
) -> dict:
    entry: dict = {
        "id": {"entry_id": entry_id},
        "parent_record_id": {"record_id": parent_record_id},
        "created_at": created_at,
    }
    entry_values: dict = {}
    if is_active is not None:
        entry_values["is_active"] = [{"active_until": None, "value": is_active}]
    if is_test is not None:
        entry_values["is_test"] = [{"active_until": None, "value": is_test}]
    if target_vertical is not None:
        entry_values["target_vertical"] = [
            {"active_until": None, "option": {"title": target_vertical}}
        ]
    if entry_values:
        entry["entry_values"] = entry_values
    return entry


def _org_record(*, is_test: bool | None = None) -> dict:
    values: dict = {}
    if is_test is not None:
        values["is_test"] = [{"active_until": None, "value": is_test}]
    return {"data": {"values": values}}


async def test_resolve_role_entry_id_finds_matching_parent() -> None:
    client = _FakeClient(entry_pages=[[_entry("entry-1", "org-a"), _entry("entry-2", "org-b")]])

    entry_id = await resolve_role_entry_id(client, "seller_role", "org-b", is_test=False)

    assert entry_id == "entry-2"
    assert client.post_calls[0][0] == "/lists/seller_role/entries/query"


async def test_resolve_role_entry_id_pages_through_multiple_pages() -> None:
    page_1 = [_entry(f"entry-{i}", f"org-{i}") for i in range(500)]
    page_2 = [_entry("entry-target", "org-target")]
    client = _FakeClient(entry_pages=[page_1, page_2])

    entry_id = await resolve_role_entry_id(client, "seller_role", "org-target", is_test=False)

    assert entry_id == "entry-target"
    assert len(client.post_calls) == 2


async def test_resolve_role_entry_id_raises_when_not_found() -> None:
    client = _FakeClient(entry_pages=[[_entry("entry-1", "org-a")]])

    with pytest.raises(RoleEntryNotFoundError):
        await resolve_role_entry_id(client, "seller_role", "org-missing", is_test=False)


async def test_resolve_role_entry_id_prefers_active_entry_over_an_earlier_stale_match() -> None:
    """The stale duplicate is listed *before* the active one — proves this
    doesn't just return whichever match pagination happens to hit first.
    """
    client = _FakeClient(
        entry_pages=[
            [
                _entry("entry-stale", "org-a", is_active=False, created_at="2024-01-01"),
                _entry("entry-active", "org-a", is_active=True, created_at="2024-06-01"),
            ]
        ]
    )

    entry_id = await resolve_role_entry_id(client, "seller_role", "org-a", is_test=False)

    assert entry_id == "entry-active"


async def test_resolve_role_entry_id_short_circuits_on_first_active_match() -> None:
    """The common, zero-duplicate case: the org's one entry is active and
    sits on page 1 — must not pay for a second page just to be sure.
    """
    page_1 = [_entry("entry-target", "org-target", is_active=True, created_at="2024-01-01")]
    page_2 = [_entry("entry-other", "org-other", is_active=True, created_at="2024-01-01")]
    client = _FakeClient(entry_pages=[page_1, page_2])

    entry_id = await resolve_role_entry_id(client, "seller_role", "org-target", is_test=False)

    assert entry_id == "entry-target"
    assert len(client.post_calls) == 1


async def test_resolve_role_entry_id_falls_back_to_newest_when_none_active() -> None:
    """An org that predates `is_active` (or hasn't been reconciled yet):
    nothing is flagged, so the newest by `created_at` wins — the same
    tiebreak `reconcile_active_entry` uses.
    """
    client = _FakeClient(
        entry_pages=[
            [
                _entry("entry-old", "org-a", created_at="2024-01-01"),
                _entry("entry-new", "org-a", created_at="2024-06-01"),
            ]
        ]
    )

    entry_id = await resolve_role_entry_id(client, "seller_role", "org-a", is_test=False)

    assert entry_id == "entry-new"


async def test_unset_vertical_only_skips_entries_that_carry_a_vertical() -> None:
    """A caller with no vertical of its own -- the public buyer form -- must
    never overwrite a mandate an advisor curated per vertical.
    """
    client = _FakeClient(
        entry_pages=[
            [
                _entry("entry-health", "org-a", is_active=True, target_vertical="Fintech"),
                _entry("entry-plain", "org-a", is_active=True, created_at="2024-01-01"),
            ]
        ]
    )

    entry_id = await resolve_role_entry_id(
        client, "buyer_role", "org-a", is_test=False, unset_vertical_only=True
    )

    assert entry_id == "entry-plain"


async def test_unset_vertical_only_raises_when_every_entry_has_a_vertical() -> None:
    """`RoleEntryNotFoundError` is the caller's signal to create the org's
    unclassified entry instead of claiming one of the verticals.
    """
    client = _FakeClient(
        entry_pages=[[_entry("entry-health", "org-a", is_active=True, target_vertical="Fintech")]]
    )

    with pytest.raises(RoleEntryNotFoundError):
        await resolve_role_entry_id(
            client, "buyer_role", "org-a", is_test=False, unset_vertical_only=True
        )


async def test_patch_organization_targets_records_endpoint() -> None:
    client = _FakeClient()

    await patch_organization(client, "org-attio-id", {"name": "New Name"})

    path, body = client.patch_calls[0]
    assert path == "/objects/organizations/records/org-attio-id"
    assert body == {"data": {"values": {"name": "New Name"}}}


async def test_patch_role_entry_targets_entries_endpoint() -> None:
    client = _FakeClient()

    await patch_role_entry(client, "seller_role", "entry-123", {"outreach_tier": "opt-1"})

    path, body = client.patch_calls[0]
    assert path == "/lists/seller_role/entries/entry-123"
    assert body == {"data": {"entry_values": {"outreach_tier": "opt-1"}}}


class _FakeCreateClient:
    def __init__(self, response: dict) -> None:
        self._response = response
        self.post_calls: list[tuple[str, dict]] = []

    async def post(self, path: str, json_body: dict) -> dict:
        self.post_calls.append((path, json_body))
        return self._response

    async def get(self, path: str) -> dict:
        raise AssertionError("not used by this test")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")


async def test_create_organization_targets_records_endpoint_and_returns_record_id() -> None:
    client = _FakeCreateClient({"data": {"id": {"record_id": "org-new-1"}}})

    record_id, web_url = await create_organization(client, is_test=False, values={"name": "New Co"})

    path, body = client.post_calls[0]
    assert path == "/objects/organizations/records"
    assert body == {"data": {"values": {"name": "New Co", "is_test": False}}}
    assert record_id == "org-new-1"
    assert web_url is None


async def test_create_role_entry_targets_entries_endpoint_and_returns_entry_id() -> None:
    client = _FakeCreateClient({"data": {"id": {"entry_id": "entry-new-1"}}})

    entry_id = await create_role_entry(
        client, "seller_role", "org-new-1", {"outreach_tier": "opt-1"}, is_test=False
    )

    path, body = client.post_calls[0]
    assert path == "/lists/seller_role/entries"
    assert body == {
        "data": {
            "parent_record_id": "org-new-1",
            "parent_object": "organizations",
            "entry_values": {"outreach_tier": "opt-1", "is_active": True, "is_test": False},
        }
    }
    assert entry_id == "entry-new-1"


async def test_create_role_entry_always_sets_is_active_true() -> None:
    """A freshly created entry is by definition the only one this bot knows
    of for the org — `_reconcile_active_entry` reads `is_active` to pick a
    winner among siblings, so a new entry can't be left `null` until that
    reconciliation happens to run.
    """
    client = _FakeCreateClient({"data": {"id": {"entry_id": "entry-new-2"}}})

    await create_role_entry(client, "buyer_role", "org-new-2", {}, is_test=False)

    _, body = client.post_calls[0]
    assert body["data"]["entry_values"]["is_active"] is True


# ---------------------------------------------------------------------------
# is_test — one SOURCE workspace, two environments
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("is_test", [True, False])
async def test_create_organization_stamps_the_scope(is_test: bool) -> None:
    client = _FakeCreateClient({"data": {"id": {"record_id": "org-new-3"}}})

    await create_organization(client, {"name": "New Co"}, is_test=is_test)

    _, body = client.post_calls[0]
    assert body["data"]["values"]["is_test"] is is_test


@pytest.mark.parametrize("is_test", [True, False])
async def test_create_role_entry_stamps_the_scope(is_test: bool) -> None:
    client = _FakeCreateClient({"data": {"id": {"entry_id": "entry-new-3"}}})

    await create_role_entry(client, "seller_role", "org-new-3", {}, is_test=is_test)

    _, body = client.post_calls[0]
    assert body["data"]["entry_values"]["is_test"] is is_test


async def test_creates_do_not_mutate_the_callers_values() -> None:
    """The caller reuses `values` to build the Postgres write; stamping into
    it in place would leak `is_test` into a table that has no such column."""
    client = _FakeCreateClient({"data": {"id": {"record_id": "org-new-4"}}})
    values = {"name": "New Co"}

    await create_organization(client, values, is_test=True)

    assert values == {"name": "New Co"}


async def test_patch_organization_does_not_send_is_test() -> None:
    """`is_test` says where a record came from, not who is editing it.
    Re-asserting it on a patch is the exact corruption the scope guard
    exists to prevent: a dev edit would make a production record vanish."""
    client = _FakeClient()

    await patch_organization(client, "org-1", {"name": "Renamed"})

    _, body = client.patch_calls[0]
    assert "is_test" not in body["data"]["values"]


async def test_patch_role_entry_does_not_send_is_test() -> None:
    client = _FakeClient()

    await patch_role_entry(client, "seller_role", "entry-1", {"outreach_tier": "opt-1"})

    _, body = client.patch_calls[0]
    assert "is_test" not in body["data"]["entry_values"]


async def test_resolve_role_entry_id_ignores_entries_from_the_other_scope() -> None:
    client = _FakeClient(
        entry_pages=[
            [
                _entry("entry-test", "org-a", is_active=True, is_test=True),
                _entry("entry-prod", "org-a", is_active=True, is_test=False),
            ]
        ]
    )

    prod = await resolve_role_entry_id(client, "seller_role", "org-a", is_test=False)
    test = await resolve_role_entry_id(client, "seller_role", "org-a", is_test=True)

    assert (prod, test) == ("entry-prod", "entry-test")


async def test_resolve_role_entry_id_raises_when_only_the_other_scope_matches() -> None:
    client = _FakeClient(entry_pages=[[_entry("entry-prod", "org-a", is_active=True)]])

    with pytest.raises(RoleEntryNotFoundError):
        await resolve_role_entry_id(client, "seller_role", "org-a", is_test=True)


class _FakeGetClient:
    def __init__(self, response: dict) -> None:
        self._response = response
        self.get_calls: list[str] = []

    async def get(self, path: str) -> dict:
        self.get_calls.append(path)
        return self._response

    async def post(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")


@pytest.mark.parametrize("is_test", [True, False])
async def test_assert_organization_in_scope_allows_a_matching_record(is_test: bool) -> None:
    client = _FakeGetClient(_org_record(is_test=is_test))

    await assert_organization_in_scope(client, "org-1", is_test=is_test)

    assert client.get_calls == ["/objects/organizations/records/org-1"]


@pytest.mark.parametrize("is_test", [True, False])
async def test_assert_organization_in_scope_raises_on_mismatch(is_test: bool) -> None:
    client = _FakeGetClient(_org_record(is_test=not is_test))

    with pytest.raises(ScopeMismatchError):
        await assert_organization_in_scope(client, "org-1", is_test=is_test)


async def test_assert_organization_in_scope_reads_unset_is_test_as_production() -> None:
    """Every record migrated before 2026-09-07 has no `is_test` value at
    all. Treating those as test would lock production out of editing its own
    records."""
    client = _FakeGetClient(_org_record())

    await assert_organization_in_scope(client, "org-1", is_test=False)

    with pytest.raises(ScopeMismatchError):
        await assert_organization_in_scope(client, "org-1", is_test=True)


# ---------------------------------------------------------------------------
# person — query-then-create/patch, not an upsert (email isn't unique)
# ---------------------------------------------------------------------------


def _person_record(record_id: str, *, is_test: bool | None = None) -> dict:
    values: dict = {}
    if is_test is not None:
        values["is_test"] = [{"active_until": None, "value": is_test}]
    return {"id": {"record_id": record_id}, "values": values}


class _FakeQueryClient:
    def __init__(self, response: dict) -> None:
        self._response = response
        self.post_calls: list[tuple[str, dict]] = []

    async def post(self, path: str, json_body: dict) -> dict:
        self.post_calls.append((path, json_body))
        return self._response

    async def get(self, path: str) -> dict:
        raise AssertionError("not used by this test")

    async def patch(self, path: str, json_body: dict) -> dict:
        raise AssertionError("not used by this test")


async def test_find_people_by_email_queries_the_person_object() -> None:
    client = _FakeQueryClient({"data": [_person_record("person-1", is_test=False)]})

    matches = await find_people_by_email(client, "dana@acme.com", is_test=False)

    path, body = client.post_calls[0]
    assert path == "/objects/person/records/query"
    assert body == {
        "filter": {"email": {"$eq": "dana@acme.com"}},
        "sorts": [{"attribute": "created_at", "direction": "asc"}],
        "limit": 500,
    }
    assert [r["id"]["record_id"] for r in matches] == ["person-1"]


async def test_find_people_by_email_filters_out_the_other_scope() -> None:
    client = _FakeQueryClient(
        {
            "data": [
                _person_record("person-test", is_test=True),
                _person_record("person-prod", is_test=False),
            ]
        }
    )

    prod = await find_people_by_email(client, "dana@acme.com", is_test=False)
    test = await find_people_by_email(client, "dana@acme.com", is_test=True)

    assert [r["id"]["record_id"] for r in prod] == ["person-prod"]
    assert [r["id"]["record_id"] for r in test] == ["person-test"]


async def test_find_people_by_email_reads_unset_is_test_as_production() -> None:
    """Same null policy as `assert_organization_in_scope` — a pre-migration
    person record with no `is_test` at all must still be found by the
    production instance, or it gets duplicated."""
    client = _FakeQueryClient({"data": [_person_record("person-1")]})

    prod = await find_people_by_email(client, "dana@acme.com", is_test=False)
    test = await find_people_by_email(client, "dana@acme.com", is_test=True)

    assert [r["id"]["record_id"] for r in prod] == ["person-1"]
    assert test == []


async def test_create_person_targets_records_endpoint_and_returns_record_id() -> None:
    client = _FakeCreateClient({"data": {"id": {"record_id": "person-new-1"}}})

    record_id = await create_person(
        client, {"name": "Dana", "email": "dana@acme.com"}, is_test=False
    )

    path, body = client.post_calls[0]
    assert path == "/objects/person/records"
    assert body == {
        "data": {"values": {"name": "Dana", "email": "dana@acme.com", "is_test": False}}
    }
    assert record_id == "person-new-1"


@pytest.mark.parametrize("is_test", [True, False])
async def test_create_person_stamps_the_scope(is_test: bool) -> None:
    client = _FakeCreateClient({"data": {"id": {"record_id": "person-new-2"}}})

    await create_person(client, {"name": "Dana"}, is_test=is_test)

    _, body = client.post_calls[0]
    assert body["data"]["values"]["is_test"] is is_test


async def test_patch_person_targets_records_endpoint() -> None:
    client = _FakeClient()

    await patch_person(client, "person-1", {"linkedin": "https://linkedin.com/in/dana"})

    path, body = client.patch_calls[0]
    assert path == "/objects/person/records/person-1"
    assert body == {"data": {"values": {"linkedin": "https://linkedin.com/in/dana"}}}


async def test_resolve_role_entry_id_only_entry_id_picks_that_entry_of_a_split_org() -> None:
    """An org split by vertical has several active entries; the edit must
    land on the role's own, not whichever active one is listed first."""
    client = _FakeClient(
        entry_pages=[
            [
                _entry("entry-clinic", "org-a", is_active=True),
                _entry("entry-fintech", "org-a", is_active=True),
            ]
        ]
    )

    entry_id = await resolve_role_entry_id(
        client, "buyer_role", "org-a", is_test=False, only_entry_id="entry-fintech"
    )

    assert entry_id == "entry-fintech"


async def test_resolve_role_entry_id_only_entry_id_still_respects_the_test_scope() -> None:
    client = _FakeClient(
        entry_pages=[[_entry("entry-test", "org-a", is_active=True, is_test=True)]]
    )

    with pytest.raises(RoleEntryNotFoundError):
        await resolve_role_entry_id(
            client, "buyer_role", "org-a", is_test=False, only_entry_id="entry-test"
        )


async def test_resolve_role_entry_id_only_entry_id_raises_when_the_entry_is_gone() -> None:
    client = _FakeClient(entry_pages=[[_entry("entry-other", "org-a", is_active=True)]])

    with pytest.raises(RoleEntryNotFoundError):
        await resolve_role_entry_id(
            client, "buyer_role", "org-a", is_test=False, only_entry_id="entry-missing"
        )
