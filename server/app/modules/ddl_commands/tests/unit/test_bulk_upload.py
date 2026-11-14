"""Bulk upload preview/commit logic against an in-memory fake CRM — no
database, no Attio. The fake mirrors what the real adds change: a new
organization appears under its domain, and a role under (domain, vertical).
"""

import uuid
from collections.abc import Callable, Coroutine
from dataclasses import dataclass
from types import SimpleNamespace

import pytest
from pydantic import BaseModel, Field

import app.modules.ddl_commands.api.bulk_upload as bulk
from app.modules.ddl_commands.api.bulk_store import (
    MAX_ROWS,
    CommitProgress,
    InMemoryPreviewStore,
    InvokedVia,
    PlannedRow,
    RowOutcome,
    StoredPreview,
)
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.write_errors import PartialWriteError

VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[0]
OTHER_VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[1]
SELLER_STATUS = SELLER_ROLE_FIELDS_BY_NAME["relationship_status"].options[0]
ORG_STATUS = ORGANIZATION_FIELDS_BY_NAME["relationship_status"].options[0]
SECTORS = ORGANIZATION_FIELDS_BY_NAME["sector_focus"].options


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
        self.lookups = 0

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
        self.lookups += 1
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


def accepted(result: bulk.PreviewResult | bulk.RejectedUpload) -> bulk.PreviewResult:
    assert isinstance(result, bulk.PreviewResult), result
    return result


def rejected(result: bulk.PreviewResult | bulk.RejectedUpload) -> bulk.RejectedUpload:
    assert isinstance(result, bulk.RejectedUpload), result
    return result


async def buyers_ok(rows: list[bulk.UploadRow]) -> bulk.PreviewResult:
    return accepted(await bulk.preview_buyers(rows))


async def sellers_ok(rows: list[bulk.UploadRow]) -> bulk.PreviewResult:
    return accepted(await bulk.preview_sellers(rows))


async def commit_and_wait(preview_id: uuid.UUID, requested_by: str | None = "U1") -> CommitProgress:
    preview = bulk._store.get(preview_id)
    assert preview is not None
    await bulk.run_commit(preview, requested_by)
    return bulk.status(preview_id)


async def test_one_invalid_row_rejects_the_whole_list_and_nothing_is_stored(crm: FakeCrm) -> None:
    rows = [buyer_row(n) for n in range(1, 138)]
    rows += [{"org_name": f"No domain {n}", "target_vertical": VERTICAL} for n in range(3)]

    result = rejected(await bulk.preview_buyers(rows))

    assert result.invalid == 3
    assert {p.row for p in result.problems} == {138, 139, 140}
    assert crm.lookups == 0  # refused before any database work
    assert crm.calls == []


async def test_preview_counts_the_new_rows_and_flags_the_existing_ones(crm: FakeCrm) -> None:
    for n in range(1, 19):
        crm.orgs[f"co{n}.com"] = {VERTICAL}
    rows = [buyer_row(n) for n in range(1, 138)]

    result = await buyers_ok(rows)

    assert (result.new, result.existing) == (119, 18)
    assert result.existing_rows == tuple(range(1, 19))
    assert crm.calls == []  # a preview writes nothing


async def test_commit_adds_new_rows_and_a_rerun_adds_nothing(crm: FakeCrm) -> None:
    result = await buyers_ok([buyer_row(n) for n in range(1, 6)])

    first = await commit_and_wait(result.preview_id)
    second = await commit_and_wait(result.preview_id)

    assert (first.state, first.added, first.skipped, first.failed) == ("done", 5, (), ())
    assert (second.added, len(second.skipped), second.failed) == (0, 5, ())
    assert len(crm.calls) == 5


async def test_commit_passes_mcp_and_the_signed_in_person(crm: FakeCrm) -> None:
    result = await buyers_ok([buyer_row(1)])

    await commit_and_wait(result.preview_id, requested_by="person-1")

    assert crm.calls[0].invoked_via == "mcp"
    assert crm.calls[0].requested_by == "person-1"
    assert crm.calls[0].is_new_org is True
    assert crm.calls[0].org_extracted == {"domains": ["co1.com"]}


async def test_row_added_after_preview_is_skipped_not_duplicated(crm: FakeCrm) -> None:
    result = await buyers_ok([buyer_row(1), buyer_row(2)])
    crm.orgs["co1.com"] = {VERTICAL}  # added by someone else meanwhile

    progress = await commit_and_wait(result.preview_id)

    assert progress.added == 1
    assert [o.row for o in progress.skipped] == [1]
    assert len(crm.calls) == 1


async def test_a_failed_row_is_reported_and_the_batch_continues(crm: FakeCrm) -> None:
    crm.fail_hosts = {"co2.com"}
    result = await buyers_ok([buyer_row(1), buyer_row(2), buyer_row(3)])

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
    result = await buyers_ok([buyer_row(1, hq_country="Overwritten")])

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

    result = await sellers_ok(rows)
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

    result = rejected(await bulk.preview_buyers(rows))

    by_row = {p.row: p.message for p in result.problems}
    assert by_row[1] == "org_name is required"
    assert by_row[2] == "unknown field 'nonsense'"
    assert by_row[3].startswith("value not allowed for 'model'. Allowed: ")
    assert "Model 1 (Network)" in by_row[3]  # enough to fix the row and send it again
    assert by_row[4] == "unknown field 'domains'"
    assert by_row[5] == "target_vertical is required"
    assert by_row[6].startswith("domain is required")  # a shared platform names no company
    assert result.invalid == 6


async def test_a_duplicate_in_the_list_rejects_it() -> None:
    rows: list[bulk.UploadRow] = [
        {"org_name": "A", "domain": "acme.com", "target_vertical": VERTICAL},
        {"org_name": "A again", "domain": "acme.com", "target_vertical": VERTICAL},
        {"org_name": "A other vertical", "domain": "acme.com", "target_vertical": OTHER_VERTICAL},
    ]

    result = rejected(await bulk.preview_buyers(rows))

    assert [(p.row, p.message) for p in result.problems] == [(2, "duplicate of row 1")]


async def test_a_domain_is_normalised_to_its_bare_host() -> None:
    rows: list[bulk.UploadRow] = [
        {"org_name": "A", "domain": "https://www.Acme.com/about", "target_vertical": VERTICAL},
        {"org_name": "B", "domain": "acme.com", "target_vertical": OTHER_VERTICAL},
    ]

    result = await buyers_ok(rows)

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
    result = await buyers_ok([buyer_row(1)])

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

    result = await buyers_ok([buyer_row(1), buyer_row(2)])
    preview = bulk._store.get(result.preview_id)
    assert preview is not None
    original = bulk._commit_row

    async def cancel_on_second(
        kind: bulk.UploadKind, row: PlannedRow, by: str | None, via: InvokedVia
    ) -> RowOutcome:
        if row.index == 2:
            raise asyncio.CancelledError
        return await original(kind, row, by, via)

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


def test_store_never_evicts_a_running_commit() -> None:
    store = InMemoryPreviewStore()
    running = StoredPreview(id=uuid.uuid4(), kind="buyer", rows=())
    store.save(running)
    store.set_progress(running.id, CommitProgress(state="running", total=0))
    idle = [StoredPreview(id=uuid.uuid4(), kind="buyer", rows=()) for _ in range(60)]
    for p in idle:
        store.save(p)

    assert store.progress(running.id) is not None
    assert store.get(idle[0].id) is None  # idle previews still go oldest first


def test_store_drops_the_oldest_preview_past_its_cap() -> None:
    store = InMemoryPreviewStore()
    previews = [StoredPreview(id=uuid.uuid4(), kind="seller", rows=()) for _ in range(51)]
    for p in previews:
        store.save(p)

    assert store.get(previews[0].id) is None
    assert store.get(previews[-1].id) is not None


async def test_strict_preview_rejects_the_whole_file_and_looks_nothing_up(crm: FakeCrm) -> None:
    rows: list[bulk.UploadRow] = [
        buyer_row(1),
        {"org_name": "Bad", "domain": "bad.com"},
        buyer_row(3),
    ]

    result = rejected(await bulk.preview_buyers(rows, row_numbers=[2, 3, 4], invoked_via="slack"))

    assert result.invalid == 1
    assert [(p.row, p.message) for p in result.problems] == [(3, "target_vertical is required")]
    assert crm.lookups == 0  # rejected before any database work
    assert crm.calls == []


async def test_strict_preview_reports_every_bad_row_by_its_spreadsheet_line() -> None:
    rows: list[bulk.UploadRow] = [
        buyer_row(1),
        {"org_name": "No domain", "target_vertical": VERTICAL},
        buyer_row(3),
        buyer_row(3),  # same domain and vertical as the row above
        {"org_name": "Bad model", "domain": "m.com", "target_vertical": VERTICAL, "model": "x"},
    ]

    result = rejected(
        await bulk.preview_buyers(rows, row_numbers=[2, 3, 4, 5, 6], invoked_via="slack")
    )

    assert {p.row for p in result.problems} == {3, 5, 6}
    assert next(p.message for p in result.problems if p.row == 5) == "duplicate of row 4"
    assert result.invalid == 3


async def test_strict_preview_of_a_clean_file_skips_existing_and_records_slack(
    crm: FakeCrm,
) -> None:
    crm.orgs["co1.com"] = {VERTICAL}

    result = accepted(
        await bulk.preview_buyers(
            [buyer_row(1), buyer_row(2)], row_numbers=[2, 3], invoked_via="slack"
        )
    )

    assert (result.new, result.existing, result.existing_rows) == (1, 1, (2,))
    progress = await commit_and_wait(result.preview_id)
    assert progress.added == 1
    assert crm.calls[0].invoked_via == "slack"


async def test_row_numbers_must_have_one_number_per_row() -> None:
    with pytest.raises(bulk.InvalidUploadError):
        await bulk.preview_buyers([buyer_row(1)], row_numbers=[2, 3], invoked_via="slack")


async def test_commit_hands_the_final_progress_to_the_done_callback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(bulk, "get_shared_task_runner", lambda: runner)
    result = await buyers_ok([buyer_row(1), buyer_row(2)])
    reported: list[CommitProgress] = []

    async def on_done(progress: CommitProgress) -> None:
        reported.append(progress)

    bulk.commit(result.preview_id, requested_by="U1", on_done=on_done)
    await runner.started[0]()

    assert [(p.state, p.added) for p in reported] == [("done", 2)]


async def test_a_failing_done_callback_does_not_fail_the_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runner = FakeRunner()
    monkeypatch.setattr(bulk, "get_shared_task_runner", lambda: runner)
    result = await buyers_ok([buyer_row(1)])

    async def on_done(progress: CommitProgress) -> None:
        raise RuntimeError("slack is down")

    bulk.commit(result.preview_id, requested_by="U1", on_done=on_done)
    await runner.started[0]()

    assert bulk.status(result.preview_id).state == "done"
    assert bulk.status(result.preview_id).added == 1


async def test_a_sellers_status_goes_to_the_role_and_the_org_status_to_the_org(
    crm: FakeCrm,
) -> None:
    row: bulk.UploadRow = {
        "org_name": "S",
        "domain": "s.com",
        "relationship_status": SELLER_STATUS,
        "org_relationship_status": ORG_STATUS,
    }

    result = await sellers_ok([row])
    await commit_and_wait(result.preview_id)

    assert crm.calls[0].role_extracted == {"relationship_status": SELLER_STATUS}
    assert crm.calls[0].org_extracted["relationship_status"] == ORG_STATUS


async def test_a_sellers_status_alone_is_not_copied_to_the_organization(crm: FakeCrm) -> None:
    row: bulk.UploadRow = {"org_name": "S", "domain": "s.com", "relationship_status": SELLER_STATUS}

    result = await sellers_ok([row])
    await commit_and_wait(result.preview_id)

    assert crm.calls[0].role_extracted == {"relationship_status": SELLER_STATUS}
    assert "relationship_status" not in crm.calls[0].org_extracted


async def test_an_org_only_status_in_the_role_key_is_refused() -> None:
    row: bulk.UploadRow = {"org_name": "S", "domain": "s.com", "relationship_status": ORG_STATUS}

    result = rejected(await bulk.preview_sellers([row]))

    message = result.problems[0].message
    assert message.startswith("value not allowed for 'relationship_status'. Allowed: ")
    assert SELLER_STATUS in message


async def test_a_list_with_some_unknown_options_is_refused_not_trimmed() -> None:
    row = buyer_row(1)
    row["sector_focus"] = [SECTORS[0], "Not a sector"]

    result = rejected(await bulk.preview_buyers([row]))

    assert result.invalid == 1
    assert result.problems[0].message.startswith("value not allowed for 'sector_focus'. Allowed: ")


async def test_an_organization_validation_error_names_the_organization_column(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class StrictOrganization(BaseModel):
        relationship_status: str | None = Field(default=None, max_length=1)

    monkeypatch.setattr(bulk, "OrganizationUpdate", StrictOrganization)
    row: bulk.UploadRow = {
        "org_name": "S",
        "domain": "s.com",
        "org_relationship_status": ORG_STATUS,
    }

    result = rejected(await bulk.preview_sellers([row]))

    # Not `relationship_status`, which is the seller role's own column.
    assert result.problems[0].message == "invalid 'org_relationship_status' (string_too_long)"


async def test_rows_already_in_the_crm_count_as_skipped_before_and_after_the_commit(
    crm: FakeCrm,
) -> None:
    for n in (1, 2):
        crm.orgs[f"co{n}.com"] = {VERTICAL}

    result = await buyers_ok([buyer_row(n) for n in range(1, 6)])

    assert (result.new, result.existing) == (3, 2)
    before = bulk.status(result.preview_id)
    assert before.state == "ready"
    assert [o.row for o in before.skipped] == [1, 2]  # visible before anything is added
    after = await commit_and_wait(result.preview_id)
    assert (after.added, len(after.skipped), len(after.failed)) == (3, 2, 0)
    assert all(o.reason == "already in the CRM" for o in after.skipped)


async def test_a_rerun_skips_the_earlier_existing_rows_and_the_ones_just_added(
    crm: FakeCrm,
) -> None:
    crm.orgs["co1.com"] = {VERTICAL}
    result = await buyers_ok([buyer_row(n) for n in range(1, 4)])
    await commit_and_wait(result.preview_id)

    again = await commit_and_wait(result.preview_id)

    assert (again.added, len(again.skipped)) == (0, 3)  # 1 existing at preview, 2 added since


async def test_problems_carry_structured_fields_not_just_a_message() -> None:
    rows: list[bulk.UploadRow] = [
        {"org_name": "", "domain": "a.com", "target_vertical": VERTICAL},
        {"org_name": "B", "domain": "b.com", "target_vertical": VERTICAL, "nonsense": "x"},
        {"org_name": "C", "domain": "c.com", "target_vertical": VERTICAL, "model": "nope"},
        {"org_name": "D", "domain": "d.com", "target_vertical": VERTICAL},
        {"org_name": "D again", "domain": "d.com", "target_vertical": VERTICAL},
    ]

    result = rejected(await bulk.preview_buyers(rows))

    by_row = {p.row: p for p in result.problems}
    assert (by_row[1].kind, by_row[1].field) == ("required", "org_name")
    assert (by_row[2].kind, by_row[2].field) == ("unknown_field", "nonsense")
    assert (by_row[3].kind, by_row[3].field) == ("not_allowed", "model")
    assert (by_row[5].kind, by_row[5].duplicate_of) == ("duplicate", 4)


async def test_a_row_from_claude_matches_dropdown_values_ignoring_case() -> None:
    row = buyer_row(1)
    row["target_vertical"] = VERTICAL.lower()
    row["model"] = BUYER_ROLE_FIELDS_BY_NAME["model"].options[0].upper()
    row["sector_focus"] = [SECTORS[0].lower(), f" {SECTORS[1].upper()} "]

    result = await buyers_ok([row])

    stored = bulk._store.get(result.preview_id)
    assert stored is not None
    role = stored.rows[0].role_extracted
    assert role["target_vertical"] == VERTICAL  # stored in the field's own spelling
    assert role["model"] == BUYER_ROLE_FIELDS_BY_NAME["model"].options[0]
    assert stored.rows[0].org_extracted["sector_focus"] == [SECTORS[0], SECTORS[1]]


async def test_an_owned_preview_reads_as_missing_to_anyone_else() -> None:
    result = accepted(await bulk.preview_buyers([buyer_row(1)], owner="U_ALICE"))

    assert bulk.status(result.preview_id, requested_by="U_ALICE").state == "ready"
    with pytest.raises(bulk.PreviewNotFoundError):
        bulk.status(result.preview_id, requested_by="U_BOB")
    with pytest.raises(bulk.PreviewNotFoundError):
        bulk.commit(result.preview_id, requested_by="U_BOB")
