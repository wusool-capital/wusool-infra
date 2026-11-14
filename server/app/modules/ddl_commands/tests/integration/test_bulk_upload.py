"""Bulk preview -> commit -> rerun against a real Postgres, with Attio mocked.

Everything runs inside the `db_sessionmaker` transaction, which rolls back at
teardown, so nothing persists. Hosts and the requesting person are unique per
test, so a populated database cannot collide with the rows these tests add.
"""

import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.modules.ddl_commands.api.bulk_upload as bulk
import app.modules.ddl_commands.api.buyer_write as buyer_write_module
import app.modules.ddl_commands.api.dependencies as dependencies_module
import app.modules.ddl_commands.api.seller_write as seller_write_module
from app.modules.ddl_commands.api.bulk_store import CommitProgress, InMemoryPreviewStore
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME

VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[0]
OTHER_VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[1]


async def _no_values(*_args: str, **_kwargs: str) -> dict[str, str]:
    return {}


async def _new_org(*_args: str, **_kwargs: str | bool) -> tuple[str, None]:
    return f"org-attio-{uuid.uuid4()}", None


async def _new_entry(*_args: str, **_kwargs: str | bool) -> str:
    return f"entry-{uuid.uuid4()}"


async def _in_scope(*_args: str, **_kwargs: str | bool) -> None:
    return None


@pytest.fixture(autouse=True)
def _wired(monkeypatch: pytest.MonkeyPatch, db_sessionmaker: async_sessionmaker[AsyncSession]):
    monkeypatch.setattr(bulk, "_store", InMemoryPreviewStore())
    # The service, its unit of work and the org lookups all open sessions here.
    monkeypatch.setattr(dependencies_module, "get_sessionmaker", lambda: db_sessionmaker)
    for module in (buyer_write_module, seller_write_module):
        monkeypatch.setattr(module, "build_attio_values", _no_values)
        monkeypatch.setattr(module, "create_organization", _new_org)
        monkeypatch.setattr(module, "create_role_entry", _new_entry)
        monkeypatch.setattr(module, "assert_organization_in_scope", _in_scope)
        monkeypatch.setattr(module, "get_attio_client", lambda: SimpleNamespace())


@pytest.fixture
def person() -> str:
    return f"person-{uuid.uuid4()}"


@pytest.fixture
def hosts() -> list[str]:
    run = uuid.uuid4().hex[:10]
    return [f"bulk-{run}-{n}.example.com" for n in range(6)]


def buyer_rows(hosts: list[str]) -> list[bulk.UploadRow]:
    return [
        {"org_name": f"Buyer {i}", "domain": f"https://www.{h}/", "target_vertical": VERTICAL}
        for i, h in enumerate(hosts)
    ]


async def _count_roles(
    maker: async_sessionmaker[AsyncSession], table: str, hosts: list[str]
) -> int:
    async with maker() as session:
        return (
            await session.execute(
                text(
                    f"SELECT count(*) FROM {table} r JOIN organizations o "
                    "ON o.attio_id = r.org_attio_id WHERE o.domains && CAST(:hosts AS text[])"
                ),
                {"hosts": hosts},
            )
        ).scalar_one()


async def _runs(maker: async_sessionmaker[AsyncSession], person: str):
    async with maker() as session:
        return (
            await session.execute(
                text(
                    "SELECT c.command, c.invoked_via, c.status, a.source FROM command_runs c "
                    "JOIN activities a ON a.ledger_id = c.id WHERE c.requested_by = :p"
                ),
                {"p": person},
            )
        ).all()


async def _commit(preview_id: uuid.UUID, person: str) -> CommitProgress:
    preview = bulk._store.get(preview_id)
    assert preview is not None
    await bulk.run_commit(preview, person)
    return bulk.status(preview_id)


async def test_buyer_preview_commit_and_rerun(
    db_sessionmaker: async_sessionmaker[AsyncSession], hosts: list[str], person: str
) -> None:
    rows = buyer_rows(hosts)
    # Two companies already in the CRM, added by an earlier upload.
    seeded = await bulk.preview_buyers(rows[:2])
    await _commit(seeded.preview_id, person)
    assert await _count_roles(db_sessionmaker, "buyer_roles", hosts) == 2

    preview = await bulk.preview_buyers(rows)

    assert (preview.new, preview.existing, preview.invalid) == (4, 2, 0)
    assert preview.existing_rows == (1, 2)
    assert await _count_roles(db_sessionmaker, "buyer_roles", hosts) == 2  # preview wrote nothing

    first = await _commit(preview.preview_id, person)
    assert (first.state, first.added, first.failed) == ("done", 4, ())
    assert await _count_roles(db_sessionmaker, "buyer_roles", hosts) == 6

    second = await _commit(preview.preview_id, person)
    assert (second.added, len(second.skipped), second.failed) == (0, 4, ())
    assert await _count_roles(db_sessionmaker, "buyer_roles", hosts) == 6

    runs = await _runs(db_sessionmaker, person)
    assert len(runs) == 6  # 2 seeded + 4 added; the rerun adds no records
    assert {(r.command, r.invoked_via, r.status, r.source) for r in runs} == {
        ("add_buyer", "mcp", "succeeded", "mcp")
    }


async def test_existing_company_gets_a_second_vertical_and_keeps_its_org_row(
    db_sessionmaker: async_sessionmaker[AsyncSession], hosts: list[str], person: str
) -> None:
    first = await bulk.preview_buyers(buyer_rows(hosts[:1]))
    await _commit(first.preview_id, person)
    other: list[bulk.UploadRow] = [
        {"org_name": "Renamed", "domain": hosts[0], "target_vertical": OTHER_VERTICAL}
    ]

    preview = await bulk.preview_buyers(other)
    progress = await _commit(preview.preview_id, person)

    assert (preview.new, preview.existing) == (1, 0)
    assert progress.added == 1
    assert await _count_roles(db_sessionmaker, "buyer_roles", hosts[:1]) == 2
    async with db_sessionmaker() as session:
        names = (
            (
                await session.execute(
                    text("SELECT name FROM organizations WHERE domains && CAST(:h AS text[])"),
                    {"h": hosts[:1]},
                )
            )
            .scalars()
            .all()
        )
    assert names == ["Buyer 0"]  # one organization, still under its first name


async def test_seller_preview_commit_and_rerun(
    db_sessionmaker: async_sessionmaker[AsyncSession], hosts: list[str], person: str
) -> None:
    rows: list[bulk.UploadRow] = [
        {"org_name": f"Seller {i}", "domain": h} for i, h in enumerate(hosts[:3])
    ]
    seeded = await bulk.preview_sellers(rows[:1])
    await _commit(seeded.preview_id, person)

    preview = await bulk.preview_sellers(rows)
    first = await _commit(preview.preview_id, person)
    second = await _commit(preview.preview_id, person)

    assert (preview.new, preview.existing) == (2, 1)
    assert (first.added, second.added, len(second.skipped)) == (2, 0, 2)
    assert await _count_roles(db_sessionmaker, "seller_roles", hosts[:3]) == 3
    assert {(r.command, r.invoked_via, r.source) for r in await _runs(db_sessionmaker, person)} == {
        ("add_seller", "mcp", "mcp")
    }
