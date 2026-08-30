"""Exercises the real `ON CONFLICT` upserts against a real (rolled-back)
transaction — `tests/unit/test_attio_sync_reconcile.py` already covers the
`is_active` tiebreak logic against a fake Attio client with no database
involved; this file is what actually proves the SQL/casts are valid. Skips
cleanly (via `db_sessionmaker`, see conftest.py) when no SSM tunnel is open.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wusool_db.models import Organization, Person

from ddl_commands.modules.attio_sync import upsert


async def _activity_count(
    db_sessionmaker: async_sessionmaker[AsyncSession], subject_type: str, subject_id: str
) -> int:
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM activities "
                    "WHERE subject_type = :t AND (subject_attio_id = :id OR subject_uuid::text = :id)"
                ),
                {"t": subject_type, "id": subject_id},
            )
        ).scalar_one()


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
    assert await _activity_count(db_sessionmaker, "Organization", attio_id) == 1


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


async def test_delete_person_sets_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    person_id = f"test-person-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Person(attio_id=person_id, name="Test Person"))
        await session.commit()

    await upsert.delete_person(person_id)

    async with db_sessionmaker() as session:
        removed_at = (
            await session.execute(
                text("SELECT removed_at FROM person WHERE attio_id = :id"), {"id": person_id}
            )
        ).scalar_one()
    assert removed_at is not None


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

    # Every DEV entry gets its own row (legacy_entry_id is the unique key,
    # not org_attio_id, since the 2026-08-28 migration) -- both entry-new
    # and entry-old must exist, is_active telling them apart.
    async with db_sessionmaker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT id, legacy_entry_id, model, is_active FROM buyer_roles "
                    "WHERE org_attio_id = :id ORDER BY legacy_entry_id"
                ),
                {"id": org_id},
            )
        ).all()
    by_entry = {r.legacy_entry_id: r for r in rows}
    assert set(by_entry) == {"entry-new", "entry-old"}
    assert by_entry["entry-new"].model == "Financial"
    assert by_entry["entry-new"].is_active is True
    assert by_entry["entry-old"].model == "Strategic"
    assert by_entry["entry-old"].is_active is False

    # And Attio's own is_active flags got corrected: new -> true, old -> false.
    assert (
        "/lists/buyer_role/entries/entry-new",
        {"data": {"entry_values": {"is_active": True}}},
    ) in client.patch_calls
    assert (
        "/lists/buyer_role/entries/entry-old",
        {"data": {"entry_values": {"is_active": False}}},
    ) in client.patch_calls

    # The activity is logged against the triggering entry's own row id
    # (entry-new, since that's what sync_buyer_role was called with), not
    # every sibling touched by the reconciliation.
    assert await _activity_count(db_sessionmaker, "BuyerRole", str(by_entry["entry-new"].id)) == 1
    assert await _activity_count(db_sessionmaker, "BuyerRole", str(by_entry["entry-old"].id)) == 0


async def test_sync_deal_fetches_from_source_object_slug(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """SOURCE Attio's custom deal object is slug "deal" (singular, not
    "deals") -- see `config.py`'s `attio_deal_object_slug`. Same `deals`
    Postgres table either way."""
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    attio_id = f"test-deal-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/deal/records/{attio_id}": {
                "data": {"id": {"record_id": attio_id}, "values": {"name": [_item(value="Deal X")]}}
            }
        }
    )

    await upsert.sync_deal(client, attio_id, object_slug="deal")

    async with db_sessionmaker() as session:
        row = (
            await session.execute(
                text("SELECT name FROM deals WHERE attio_id = :id"), {"id": attio_id}
            )
        ).one()
    assert row.name == "Deal X"
    assert await _activity_count(db_sessionmaker, "Deal", attio_id) == 1


async def test_sync_note_resolves_org_and_role_references(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Test Org"))
        await session.commit()

    note_id = str(uuid.uuid4())
    client = _FakeClient(
        {
            f"/objects/note/records/{note_id}": {
                "data": {
                    "id": {"record_id": note_id},
                    "values": {
                        "organization_id": [_item(target_record_id=org_id)],
                        "note_type": [_item(value="Manual")],
                        "content": [_item(value="Called the seller, went well.")],
                    },
                }
            }
        }
    )

    await upsert.sync_note(client, note_id)

    async with db_sessionmaker() as session:
        row = (
            await session.execute(
                text(
                    "SELECT organization_id, person_id, note_type, content FROM notes WHERE id = :id"
                ),
                {"id": note_id},
            )
        ).one()
    assert row.organization_id == org_id
    assert row.person_id is None
    assert row.note_type == "Manual"
    assert row.content == "Called the seller, went well."
    assert await _activity_count(db_sessionmaker, "Note", note_id) == 1


async def test_sync_note_is_idempotent(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    note_id = str(uuid.uuid4())
    client = _FakeClient(
        {
            f"/objects/note/records/{note_id}": {
                "data": {
                    "id": {"record_id": note_id},
                    "values": {
                        "note_type": [_item(value="Manual")],
                        "content": [_item(value="First version")],
                    },
                }
            }
        }
    )

    await upsert.sync_note(client, note_id)
    await upsert.sync_note(client, note_id)  # must not raise or duplicate

    async with db_sessionmaker() as session:
        count = (
            await session.execute(text("SELECT count(*) FROM notes WHERE id = :id"), {"id": note_id})
        ).scalar_one()
    assert count == 1
