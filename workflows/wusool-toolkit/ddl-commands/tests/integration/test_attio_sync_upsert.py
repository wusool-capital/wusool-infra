"""Exercises the real `ON CONFLICT` upserts against a real (rolled-back)
transaction — `tests/unit/test_attio_sync_reconcile.py` already covers the
`is_active` tiebreak logic against a fake Attio client with no database
involved; this file is what actually proves the SQL/casts are valid. Skips
cleanly (via `db_sessionmaker`, see conftest.py) when no SSM tunnel is open.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wusool_db.models import Organization

from ddl_commands.modules.attio_sync import upsert


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


class _FakeClient:
    """Serves whatever canned responses a test hands it, keyed by path."""

    def __init__(self, get_responses: dict[str, dict] | None = None) -> None:
        self._get_responses = get_responses or {}
        self.patch_calls: list[tuple[str, dict]] = []
        self._entry_pages: dict[str, list[list[dict]]] = {}

    def add_entry_pages(self, list_slug: str, pages: list[list[dict]]) -> None:
        self._entry_pages[list_slug] = pages

    async def get(self, path: str) -> dict:
        return self._get_responses[path]

    async def post(self, path: str, json_body: dict) -> dict:
        list_slug = path.split("/")[2]
        pages = self._entry_pages.get(list_slug, [])
        offset = json_body["offset"]
        page_index = offset // json_body["limit"]
        page = pages[page_index] if page_index < len(pages) else []
        return {"data": page}

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patch_calls.append((path, json_body))
        return {}


async def test_sync_organization_inserts_a_new_row(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    attio_id = f"test-org-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/organizations/records/{attio_id}": {
                "data": {
                    "id": {"record_id": attio_id},
                    "values": {
                        "name": [_item(value="Zephyr Manufacturing")],
                        "hq_country": [_item(value="AE")],
                        "sector_focus": [_item(option={"title": "Industrials"})],
                    },
                }
            }
        }
    )

    await upsert.sync_organization(client, attio_id)

    async with db_sessionmaker() as session:
        row = (
            await session.execute(
                text(
                    "SELECT name, hq_country, sector_focus FROM organizations "
                    "WHERE attio_id = :id"
                ),
                {"id": attio_id},
            )
        ).one()
    assert row.name == "Zephyr Manufacturing"
    assert row.hq_country == "AE"
    assert row.sector_focus == ["Industrials"]


async def test_sync_organization_is_idempotent(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    attio_id = f"test-org-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/organizations/records/{attio_id}": {
                "data": {"id": {"record_id": attio_id}, "values": {"name": [_item(value="Acme")]}}
            }
        }
    )

    await upsert.sync_organization(client, attio_id)
    await upsert.sync_organization(client, attio_id)  # must not raise or duplicate

    async with db_sessionmaker() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM organizations WHERE attio_id = :id"), {"id": attio_id}
            )
        ).scalar_one()
    assert count == 1


async def test_sync_buyer_role_reconciles_and_upserts(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    # Deliberately not the `throwaway_org` fixture: it's built on `db_session`,
    # a separate connection/transaction from `db_sessionmaker` — the FK'd org
    # row it creates would be invisible to sync_buyer_role's own queries here,
    # which all run through db_sessionmaker's connection instead. Creating the
    # org through that same sessionmaker keeps everything on one transaction.
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(
            Organization(
                attio_id=org_id, name="Test Org", hq_country="AE", sector_focus=["Healthcare"]
            )
        )
        await session.commit()

    older_entry = {
        "id": {"entry_id": "entry-old"},
        "parent_record_id": {"record_id": org_id},
        "created_at": "2024-01-01T00:00:00Z",
        "entry_values": {
            "is_active": [_item(value=True)],
            "model": [_item(option={"title": "Strategic"})],
        },
    }
    newer_entry = {
        "id": {"entry_id": "entry-new"},
        "parent_record_id": {"record_id": org_id},
        "created_at": "2024-01-03T00:00:00Z",
        "entry_values": {"model": [_item(option={"title": "Financial"})]},
    }
    client = _FakeClient({"/lists/buyer_role/entries/entry-new": {"data": newer_entry}})
    client.add_entry_pages("buyer_role", [[older_entry, newer_entry]])

    await upsert.sync_buyer_role(client, "entry-new")

    # The newer entry won the tiebreak, so *its* values land in Postgres —
    # even though the event that triggered this was for entry-new directly.
    async with db_sessionmaker() as session:
        row = (
            await session.execute(
                text("SELECT model FROM buyer_roles WHERE org_attio_id = :id"), {"id": org_id}
            )
        ).one()
    assert row.model == "Financial"

    # And Attio's own is_active flags got corrected: new -> true, old -> false.
    assert (
        "/lists/buyer_role/entries/entry-new",
        {"data": {"entry_values": {"is_active": True}}},
    ) in client.patch_calls
    assert (
        "/lists/buyer_role/entries/entry-old",
        {"data": {"entry_values": {"is_active": False}}},
    ) in client.patch_calls
