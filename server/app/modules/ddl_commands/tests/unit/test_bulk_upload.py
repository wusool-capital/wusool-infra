"""Bulk upload preview/commit logic against an in-memory fake CRM — no
database, no Attio. The fake mirrors what the real adds change: a new
organization appears under its domain, and a role under (domain, vertical).
"""

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from types import SimpleNamespace

import pytest

import app.modules.ddl_commands.api.bulk_upload as bulk
from app.modules.ddl_commands.api.bulk_store import (
    MAX_ROWS,
    CommitProgress,
    InMemoryPreviewStore,
    PlannedRow,
    StoredPreview,
)
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.write_errors import PartialWriteError

VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[0]
OTHER_VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[1]


@dataclass(frozen=True)
class AddCall:
    is_new_org: bool
    org_attio_id: str | None
    org_name: str | None
    org_extracted: bulk.UploadRow
    role_extracted: bulk.UploadRow
    requested_by: str | None
    invoked_via: str


class FakeCrm:
    """`orgs` maps a host to its buyer verticals; `sellers` is hosts with an active seller."""

    def __init__(self) -> None:
        self.orgs: dict[str, set[PrefillValue | None]] = {}
        self.sellers: set[str] = set()
        self.calls: list[AddCall] = []
        self.fail_hosts: set[str] = set()

    @staticmethod
    def _host(org_attio_id: str) -> str:
        return org_attio_id.removeprefix("org-")

    def _target(self, call: AddCall) -> str:
        if call.is_new_org:
            domains = call.org_extracted["domains"]
            assert isinstance(domains, list)
            return domains[0]
        assert call.org_attio_id is not None
        return self._host(call.org_attio_id)

    async def find_organization_by_domains(self, hosts: list[str]) -> SimpleNamespace | None:
        for host in hosts:
            if host in self.orgs:
                return SimpleNamespace(attio_id=f"org-{host}")
        return None

    async def buyer_exists(self, org_attio_id: str, vertical: str | None) -> bool:
        return vertical in self.orgs.get(self._host(org_attio_id), set())

    async def resolve_organization(self, org_attio_id: str) -> SimpleNamespace:
        active = self._host(org_attio_id) in self.sellers
        return SimpleNamespace(seller_roles=[SimpleNamespace(is_active=True)] if active else [])

    async def write_buyer_add(
        self,
        *,
        is_new_org: bool,
        org_attio_id: str | None,
        org_name: str | None,
        org_extracted: bulk.UploadRow,
        role_extracted: bulk.UploadRow,
        requested_by: str | None,
        invoked_via: str,
    ) -> None:
        call = AddCall(
            is_new_org,
            org_attio_id,
            org_name,
            org_extracted,
            role_extracted,
            requested_by,
            invoked_via,
        )
        host = self._target(call)
        if host in self.fail_hosts:
            raise PartialWriteError(["organization created in Attio"], RuntimeError("boom"))
        self.orgs.setdefault(host, set()).add(role_extracted["target_vertical"])
        self.calls.append(call)

    async def write_seller_add(
        self,
        *,
        is_new_org: bool,
        org_attio_id: str | None,
        org_name: str | None,
        org_extracted: bulk.UploadRow,
        role_extracted: bulk.UploadRow,
        requested_by: str | None,
        invoked_via: str,
    ) -> None:
        call = AddCall(
            is_new_org,
            org_attio_id,
            org_name,
            org_extracted,
            role_extracted,
            requested_by,
            invoked_via,
        )
        host = self._target(call)
        self.orgs.setdefault(host, set())
        self.sellers.add(host)
        self.calls.append(call)


class FakeRunner:
    def __init__(self) -> None:
        self.started: list[Callable[[], Coroutine[None, None, None]]] = []

    def run(self, coro_factory: Callable[[], Coroutine[None, None, None]], *, name: str) -> None:
        self.started.append(coro_factory)


@pytest.fixture(autouse=True)
def crm(monkeypatch: pytest.MonkeyPatch) -> FakeCrm:
    fake = FakeCrm()
    monkeypatch.setattr(bulk, "_store", InMemoryPreviewStore())
    monkeypatch.setattr(bulk, "find_organization_by_domains", fake.find_organization_by_domains)
    monkeypatch.setattr(
        bulk, "ddl_commands_service", lambda: SimpleNamespace(buyer_exists=fake.buyer_exists)
    )
    monkeypatch.setattr(bulk, "resolve_organization", fake.resolve_organization)
    monkeypatch.setattr(bulk, "write_buyer_add", fake.write_buyer_add)
    monkeypatch.setattr(bulk, "write_seller_add", fake.write_seller_add)
    return fake


def buyer_row(n: int, **extra: str) -> bulk.UploadRow:
    return {"org_name": f"Co {n}", "domain": f"co{n}.com", "target_vertical": VERTICAL, **extra}


async def commit_and_wait(preview_id: uuid.UUID, requested_by: str | None = "U1") -> CommitProgress:
    preview = bulk._store.get(preview_id)
    assert preview is not None
    await bulk.run_commit(preview, requested_by)
    return bulk.status(preview_id)


async def test_preview_flags_existing_and_invalid_and_writes_nothing(crm: FakeCrm) -> None:
    for n in range(1, 19):
        crm.orgs[f"co{n}.com"] = {VERTICAL}
    rows = [buyer_row(n) for n in range(1, 138)]
    rows += [{"org_name": f"No domain {n}", "target_vertical": VERTICAL} for n in range(3)]

    result = await bulk.preview_buyers(rows)

    assert (result.new, result.existing, result.invalid) == (119, 18, 3)
    assert result.existing_rows == tuple(range(1, 19))
    assert {p.row for p in result.problems} == {138, 139, 140}
    assert crm.calls == []


async def test_commit_adds_new_rows_and_a_rerun_adds_nothing(crm: FakeCrm) -> None:
    result = await bulk.preview_buyers([buyer_row(n) for n in range(1, 6)])

    first = await commit_and_wait(result.preview_id)
    second = await commit_and_wait(result.preview_id)

    assert (first.state, first.added, first.skipped, first.failed) == ("done", 5, (), ())
    assert (second.added, len(second.skipped), second.failed) == (0, 5, ())
    assert len(crm.calls) == 5


async def test_commit_passes_mcp_and_the_signed_in_person(crm: FakeCrm) -> None:
    result = await bulk.preview_buyers([buyer_row(1)])

    await commit_and_wait(result.preview_id, requested_by="person-1")

    assert crm.calls[0].invoked_via == "mcp"
    assert crm.calls[0].requested_by == "person-1"
    assert crm.calls[0].is_new_org is True
    assert crm.calls[0].org_extracted == {"domains": ["co1.com"]}


async def test_row_added_after_preview_is_skipped_not_duplicated(crm: FakeCrm) -> None:
    result = await bulk.preview_buyers([buyer_row(1), buyer_row(2)])
    crm.orgs["co1.com"] = {VERTICAL}  # added by someone else meanwhile

    progress = await commit_and_wait(result.preview_id)

    assert progress.added == 1
    assert [o.row for o in progress.skipped] == [1]
    assert len(crm.calls) == 1


async def test_a_failed_row_is_reported_and_the_batch_continues(crm: FakeCrm) -> None:
    crm.fail_hosts = {"co2.com"}
    result = await bulk.preview_buyers([buyer_row(1), buyer_row(2), buyer_row(3)])

    progress = await commit_and_wait(result.preview_id)

    assert progress.added == 2
    assert [o.row for o in progress.failed] == [2]
    reason = progress.failed[0].reason or ""
    assert "RuntimeError" in reason and "organization created in Attio" in reason
    assert "boom" not in reason  # type only, never the message


async def test_existing_org_with_a_new_vertical_gets_a_role_and_no_org_changes(
    crm: FakeCrm,
) -> None:
    crm.orgs["co1.com"] = {OTHER_VERTICAL}
    result = await bulk.preview_buyers([buyer_row(1, hq_country="Overwritten")])

    assert (result.new, result.existing) == (1, 0)
    await commit_and_wait(result.preview_id)

    assert crm.calls[0].is_new_org is False
    assert crm.calls[0].org_attio_id == "org-co1.com"
    assert crm.calls[0].org_extracted == {}  # our data wins


async def test_seller_with_an_active_role_is_existing_whatever_the_sector(crm: FakeCrm) -> None:
    crm.orgs["co1.com"] = set()
    crm.sellers.add("co1.com")
    rows: list[bulk.UploadRow] = [
        {"org_name": "Co 1", "domain": "co1.com"},
        {"org_name": "Co 2", "domain": "co2.com"},
    ]

    result = await bulk.preview_sellers(rows)
    progress = await commit_and_wait(result.preview_id)

    assert (result.new, result.existing) == (1, 1)
    assert progress.added == 1
    assert crm.calls[0].org_name == "Co 2"


async def test_row_problems_are_specific_and_never_echo_values() -> None:
    rows: list[bulk.UploadRow] = [
        {"org_name": " ", "domain": "a.com", "target_vertical": VERTICAL},
        {"org_name": "B", "domain": "b.com", "target_vertical": VERTICAL, "nonsense": "x"},
        {"org_name": "C", "domain": "c.com", "target_vertical": VERTICAL, "model": "nope"},
        {"org_name": "D", "domain": "d.com", "target_vertical": VERTICAL, "domains": ["z.com"]},
        {"org_name": "E", "domain": "e.com"},
        {"org_name": "F", "domain": "instagram.com/f", "target_vertical": VERTICAL},
    ]

    result = await bulk.preview_buyers(rows)

    by_row = {p.row: p.message for p in result.problems}
    assert by_row[1] == "org_name is required"
    assert by_row[2] == "unknown field 'nonsense'"
    assert by_row[3] == "value not allowed for 'model'"
    assert by_row[4] == "unknown field 'domains'"
    assert by_row[5] == "target_vertical is required"
    assert by_row[6].startswith("domain is required")  # a shared platform names no company
    assert (result.new, result.invalid) == (0, 6)


async def test_domain_is_normalised_and_in_batch_duplicates_are_flagged() -> None:
    rows: list[bulk.UploadRow] = [
        {"org_name": "A", "domain": "https://www.Acme.com/about", "target_vertical": VERTICAL},
        {"org_name": "A again", "domain": "acme.com", "target_vertical": VERTICAL},
        {"org_name": "A other vertical", "domain": "acme.com", "target_vertical": OTHER_VERTICAL},
    ]

    result = await bulk.preview_buyers(rows)

    assert (result.new, result.invalid) == (2, 1)
    assert result.problems[0].row == 2
    assert result.problems[0].message == "duplicate of row 1"
    stored = bulk._store.get(result.preview_id)
    assert stored is not None
    assert {r.domain for r in stored.rows} == {"acme.com"}


@pytest.mark.parametrize("count", [0, MAX_ROWS + 1])
async def test_preview_rejects_an_empty_or_oversized_upload(count: int) -> None:
    with pytest.raises(bulk.InvalidUploadError):
        await bulk.preview_buyers([buyer_row(n) for n in range(count)])


async def test_commit_runs_in_the_background_and_is_not_started_twice(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(bulk, "get_shared_task_runner", lambda: runner)
    result = await bulk.preview_buyers([buyer_row(1)])

    first = bulk.commit(result.preview_id, requested_by="U1")
    second = bulk.commit(result.preview_id, requested_by="U1")

    assert (first.state, second.state) == ("running", "running")
    assert len(runner.started) == 1


async def test_unknown_or_expired_preview_is_not_found() -> None:
    with pytest.raises(bulk.PreviewNotFoundError):
        bulk.status(uuid.uuid4())
    with pytest.raises(bulk.PreviewNotFoundError):
        bulk.commit(uuid.uuid4(), requested_by=None)


async def test_a_cancelled_commit_is_marked_interrupted_so_it_can_resume(
    crm: FakeCrm, monkeypatch: pytest.MonkeyPatch
) -> None:
    import asyncio

    result = await bulk.preview_buyers([buyer_row(1), buyer_row(2)])
    preview = bulk._store.get(result.preview_id)
    assert preview is not None
    original = bulk._commit_row

    async def cancel_on_second(kind: bulk.UploadKind, row: PlannedRow, by: str | None):  # noqa: ANN202
        if row.index == 2:
            raise asyncio.CancelledError
        return await original(kind, row, by)

    monkeypatch.setattr(bulk, "_commit_row", cancel_on_second)
    with pytest.raises(asyncio.CancelledError):
        await bulk.run_commit(preview, "U1")

    assert bulk.status(result.preview_id).state == "interrupted"
    assert bulk.status(result.preview_id).added == 1


def test_store_expires_previews_and_a_write_extends_the_life() -> None:
    now = [0.0]
    store = InMemoryPreviewStore(ttl_seconds=10, clock=lambda: now[0])
    preview = StoredPreview(id=uuid.uuid4(), kind="buyer", rows=())
    store.save(preview)

    now[0] = 9
    store.set_progress(preview.id, CommitProgress(state="running", total=0))
    now[0] = 18  # past the first expiry, inside the extended one
    assert store.get(preview.id) is not None
    now[0] = 29
    assert store.get(preview.id) is None
    assert store.progress(preview.id) is None


def test_store_drops_the_oldest_preview_past_its_cap() -> None:
    store = InMemoryPreviewStore()
    previews = [StoredPreview(id=uuid.uuid4(), kind="seller", rows=()) for _ in range(51)]
    for p in previews:
        store.save(p)

    assert store.get(previews[0].id) is None
    assert store.get(previews[-1].id) is not None
