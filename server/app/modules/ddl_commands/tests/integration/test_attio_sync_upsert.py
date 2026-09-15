"""Exercises the real `ON CONFLICT` upserts against a real (rolled-back)
transaction — `tests/unit/test_attio_sync_reconcile.py` already covers the
`is_active` tiebreak logic against a fake Attio client with no database
involved; this file is what actually proves the SQL/casts are valid. Skips
cleanly (via `db_sessionmaker`, see conftest.py) when no SSM tunnel is open.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import BuyerRole, Deal, Note, Organization, Person, SellerRole
from app.modules.ddl_commands.persistence import attio_sync as upsert


async def _activity_count(
    db_sessionmaker: async_sessionmaker[AsyncSession], subject_type: str, subject_id: str
) -> int:
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text(
                    "SELECT count(*) FROM activities WHERE subject_type = :t "
                    "AND (subject_attio_id = :id OR subject_uuid::text = :id)"
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
                    "SELECT name, hq_country, sector_focus FROM organizations WHERE attio_id = :id"
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


async def test_upsert_batch_inserts_multiple_organizations(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    ids = [f"test-org-{uuid.uuid4()}" for _ in range(3)]
    rows = [
        dict(
            upsert._organization_params(
                {"id": {"record_id": oid}, "values": {"name": [_item(value=f"Batch Org {i}")]}}
            )
        )
        for i, oid in enumerate(ids)
    ]

    ok, failed, returned = await upsert.upsert_batch_with_retry(Organization, rows)

    assert (ok, failed) == (3, 0)
    assert set(returned) == set(ids)
    async with db_sessionmaker() as session:
        rows_in_db = (
            await session.execute(
                text("SELECT attio_id, name FROM organizations WHERE attio_id = ANY(:ids)"),
                {"ids": ids},
            )
        ).all()
    assert {r.attio_id: r.name for r in rows_in_db} == {
        oid: f"Batch Org {i}" for i, oid in enumerate(ids)
    }


async def test_upsert_batch_on_conflict_updates_existing_row(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    oid = f"test-org-{uuid.uuid4()}"
    original = dict(
        upsert._organization_params(
            {"id": {"record_id": oid}, "values": {"name": [_item(value="Original")]}}
        )
    )
    await upsert.upsert_batch_with_retry(Organization, [original])

    changed = dict(
        upsert._organization_params(
            {"id": {"record_id": oid}, "values": {"name": [_item(value="Updated")]}}
        )
    )
    ok, failed, returned = await upsert.upsert_batch_with_retry(Organization, [changed])

    assert (ok, failed) == (1, 0)
    assert returned[oid]["values"]["name"][0]["value"] == "Updated"
    async with db_sessionmaker() as session:
        name = (
            await session.execute(
                text("SELECT name FROM organizations WHERE attio_id = :id"), {"id": oid}
            )
        ).scalar_one()
    assert name == "Updated"


async def test_upsert_batch_skips_the_write_when_content_is_unchanged(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    oid = f"test-org-{uuid.uuid4()}"
    row = upsert._organization_params(
        {"id": {"record_id": oid}, "values": {"name": [_item(value="Stable Org")]}}
    )
    await upsert.upsert_batch_with_retry(Organization, [dict(row)])
    async with db_sessionmaker() as session:
        first_updated_at = (
            await session.execute(
                text("SELECT updated_at FROM organizations WHERE attio_id = :id"), {"id": oid}
            )
        ).scalar_one()

    # Re-upsert with byte-identical raw_attio -- nothing changed in Attio.
    ok, failed, returned = await upsert.upsert_batch_with_retry(Organization, [dict(row)])

    assert (ok, failed) == (1, 0)
    assert returned == {}  # skipped: no RETURNING row for an unwritten conflict
    async with db_sessionmaker() as session:
        second_updated_at = (
            await session.execute(
                text("SELECT updated_at FROM organizations WHERE attio_id = :id"), {"id": oid}
            )
        ).scalar_one()
    assert second_updated_at == first_updated_at  # write was actually skipped, not just fast


async def test_upsert_batch_still_clears_removed_at_when_content_is_unchanged(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    oid = f"test-org-{uuid.uuid4()}"
    row = upsert._organization_params(
        {"id": {"record_id": oid}, "values": {"name": [_item(value="Reappearing Org")]}}
    )
    await upsert.upsert_batch_with_retry(Organization, [dict(row)])
    await upsert.delete_organization(oid)
    async with db_sessionmaker() as session:
        removed_at = (
            await session.execute(
                text("SELECT removed_at FROM organizations WHERE attio_id = :id"), {"id": oid}
            )
        ).scalar_one()
    assert removed_at is not None

    # Org reappears in Attio with byte-identical raw_attio to before deletion
    # -- content comparison alone would see "no change" and skip the write,
    # leaving removed_at stuck forever.
    ok, failed, returned = await upsert.upsert_batch_with_retry(Organization, [dict(row)])

    assert (ok, failed) == (1, 0)
    assert oid in returned  # forced through despite unchanged content
    async with db_sessionmaker() as session:
        removed_at = (
            await session.execute(
                text("SELECT removed_at FROM organizations WHERE attio_id = :id"), {"id": oid}
            )
        ).scalar_one()
    assert removed_at is None


async def test_upsert_batch_with_retry_falls_back_to_per_row_on_a_bad_row(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    good_id = f"test-org-{uuid.uuid4()}"
    bad_id = f"test-org-{uuid.uuid4()}"
    good_row = dict(
        upsert._organization_params(
            {"id": {"record_id": good_id}, "values": {"name": [_item(value="Good Org")]}}
        )
    )
    bad_row: dict = dict(
        upsert._organization_params(
            {"id": {"record_id": bad_id}, "values": {"name": [_item(value="Bad Org")]}}
        )
    )
    bad_row["name"] = None  # violates organizations.name's NOT NULL constraint

    ok, failed, returned = await upsert.upsert_batch_with_retry(Organization, [good_row, bad_row])

    assert ok == 1
    assert failed == 1
    assert returned == {}  # the whole batch failed; nothing to content-check from it

    async with db_sessionmaker() as session:
        count = (
            await session.execute(
                text("SELECT count(*) FROM organizations WHERE attio_id = :id"), {"id": good_id}
            )
        ).scalar_one()
    assert count == 1  # the good row still landed via the per-row fallback


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

    # Both entries land in Postgres now, one row each keyed by
    # legacy_entry_id (2026-08-28 pluralization: org_attio_id is no longer
    # unique) -- the newer one as the active winner, the older as an
    # explicitly-inactive duplicate, even though the event that triggered
    # this was for entry-new directly.
    async with db_sessionmaker() as session:
        rows = (
            await session.execute(
                text(
                    "SELECT legacy_entry_id, model, is_active FROM buyer_roles "
                    "WHERE org_attio_id = :id"
                ),
                {"id": org_id},
            )
        ).all()
    by_entry = {r.legacy_entry_id: (r.model, r.is_active) for r in rows}
    assert by_entry == {
        "entry-new": ("Financial", True),
        "entry-old": ("Strategic", False),
    }

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
    async with db_sessionmaker() as session:
        winner_id = (
            await session.execute(
                text("SELECT id FROM buyer_roles WHERE legacy_entry_id = 'entry-new'")
            )
        ).scalar_one()
        loser_id = (
            await session.execute(
                text("SELECT id FROM buyer_roles WHERE legacy_entry_id = 'entry-old'")
            )
        ).scalar_one()
    assert await _activity_count(db_sessionmaker, "BuyerRole", str(winner_id)) == 1
    assert await _activity_count(db_sessionmaker, "BuyerRole", str(loser_id)) == 0


async def test_sync_deal_fetches_from_source_object_slug(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """SOURCE's custom Deal_V2 object is api_slug "deal" (singular) and
    prefixes its own fields (`deal_name`). The standard plural `deals`
    object still exists in SOURCE but is out of this sync's scope -- it has
    no `is_test` attribute, so its records could never be assigned to an
    environment. The Postgres table is named `deals` either way."""
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    attio_id = f"test-deal-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/deal/records/{attio_id}": {
                "data": {
                    "id": {"record_id": attio_id},
                    "values": {"deal_name": [_item(value="Deal X")]},
                }
            }
        }
    )

    await upsert.sync_deal(client, attio_id)

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
                        # Lowercase, as the Attio select's own option titles
                        # are -- they are the MeetingRole values, and the
                        # meeting_role cast rejects anything else.
                        "primary_role": [_item(value="seller")],
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
                    "SELECT organization_id, person_id, note_type, primary_role, "
                    "content FROM notes WHERE id = :id"
                ),
                {"id": note_id},
            )
        ).one()
    assert row.organization_id == org_id
    assert row.person_id is None
    assert row.note_type == "Manual"
    assert row.primary_role == "seller"
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
            await session.execute(
                text("SELECT count(*) FROM notes WHERE id = :id"), {"id": note_id}
            )
        ).scalar_one()
    assert count == 1


async def _removed_at(
    db_sessionmaker: async_sessionmaker[AsyncSession], table: str, key_col: str, key: str
) -> object:
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text(f"SELECT removed_at FROM {table} WHERE {key_col} = :key"),  # noqa: S608
                {"key": key},
            )
        ).scalar_one()


async def test_delete_organization_sets_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Doomed Org"))
        await session.commit()

    await upsert.delete_organization(org_id)

    assert await _removed_at(db_sessionmaker, "organizations", "attio_id", org_id) is not None


async def test_delete_deal_sets_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    deal_id = f"test-deal-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Deal(attio_id=deal_id, name="Doomed Deal"))
        await session.commit()

    await upsert.delete_deal(deal_id)

    assert await _removed_at(db_sessionmaker, "deals", "attio_id", deal_id) is not None


async def test_delete_note_sets_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Keyed on `id`, not `attio_id` -- `notes` has no `attio_id` column; for
    an Attio-originated note the primary key *is* the Attio record id."""
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    note_id = str(uuid.uuid4())
    async with db_sessionmaker() as session:
        session.add(Note(id=uuid.UUID(note_id), note_type="Manual", content="Doomed note"))
        await session.commit()

    await upsert.delete_note(note_id)

    assert await _removed_at(db_sessionmaker, "notes", "id", note_id) is not None


async def test_delete_note_leaves_a_locally_minted_note_alone(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """A note whose Attio push failed keeps a local `gen_random_uuid()` that no
    Attio record id can ever equal, so a deletion in Attio must not touch it.
    Guards the meeting summaries that exist only in Postgres.
    """
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    local_only = uuid.uuid4()
    deleted_in_attio = str(uuid.uuid4())
    async with db_sessionmaker() as session:
        session.add(Note(id=local_only, note_type="Meeting", content="Unpushed summary"))
        await session.commit()

    await upsert.delete_note(deleted_in_attio)

    assert await _removed_at(db_sessionmaker, "notes", "id", str(local_only)) is None


async def test_delete_buyer_role_sets_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Keyed on `legacy_entry_id`: `list-entry.deleted` reports the entry, and
    since the 2026-08-28 pluralization one org can hold several of them."""
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Test Org"))
        session.add(BuyerRole(org_attio_id=org_id, legacy_entry_id="entry-doomed"))
        session.add(BuyerRole(org_attio_id=org_id, legacy_entry_id="entry-survivor"))
        await session.commit()

    await upsert.delete_buyer_role("entry-doomed")

    assert (
        await _removed_at(db_sessionmaker, "buyer_roles", "legacy_entry_id", "entry-doomed")
        is not None
    )
    # The sibling entry on the same org is untouched -- the delete is per
    # entry, not per organization.
    assert (
        await _removed_at(db_sessionmaker, "buyer_roles", "legacy_entry_id", "entry-survivor")
        is None
    )


async def test_delete_seller_role_sets_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Test Org"))
        session.add(SellerRole(org_attio_id=org_id, legacy_entry_id="entry-doomed"))
        session.add(SellerRole(org_attio_id=org_id, legacy_entry_id="entry-survivor"))
        await session.commit()

    await upsert.delete_seller_role("entry-doomed")

    assert (
        await _removed_at(db_sessionmaker, "seller_roles", "legacy_entry_id", "entry-doomed")
        is not None
    )
    assert (
        await _removed_at(db_sessionmaker, "seller_roles", "legacy_entry_id", "entry-survivor")
        is None
    )


async def test_sync_organization_clears_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    """Re-creating a deleted record in Attio must bring the row back live --
    otherwise every `removed_at IS NULL` query keeps hiding a record that
    exists again. The batch path has its own test above
    (`test_upsert_batch_still_clears_removed_at_when_content_is_unchanged`);
    this is the per-event webhook path.
    """
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/organizations/records/{org_id}": {
                "data": {"id": {"record_id": org_id}, "values": {"name": [_item(value="Reborn")]}}
            }
        }
    )
    await upsert.sync_organization(client, org_id)
    await upsert.delete_organization(org_id)
    assert await _removed_at(db_sessionmaker, "organizations", "attio_id", org_id) is not None

    await upsert.sync_organization(client, org_id)

    assert await _removed_at(db_sessionmaker, "organizations", "attio_id", org_id) is None


async def test_sync_person_clears_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    person_id = f"test-person-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/person/records/{person_id}": {
                "data": {"id": {"record_id": person_id}, "values": {"name": [_item(value="Ada")]}}
            }
        }
    )
    await upsert.sync_person(client, person_id)
    await upsert.delete_person(person_id)
    assert await _removed_at(db_sessionmaker, "person", "attio_id", person_id) is not None

    await upsert.sync_person(client, person_id)

    assert await _removed_at(db_sessionmaker, "person", "attio_id", person_id) is None


async def test_sync_deal_clears_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    deal_id = f"test-deal-{uuid.uuid4()}"
    client = _FakeClient(
        {
            f"/objects/deal/records/{deal_id}": {
                "data": {
                    "id": {"record_id": deal_id},
                    "values": {"deal_name": [_item(value="Reborn Deal")]},
                }
            }
        }
    )
    await upsert.sync_deal(client, deal_id)
    await upsert.delete_deal(deal_id)
    assert await _removed_at(db_sessionmaker, "deals", "attio_id", deal_id) is not None

    await upsert.sync_deal(client, deal_id)

    assert await _removed_at(db_sessionmaker, "deals", "attio_id", deal_id) is None


async def test_sync_note_clears_removed_at(
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
                        "content": [_item(value="Reborn note")],
                    },
                }
            }
        }
    )
    await upsert.sync_note(client, note_id)
    await upsert.delete_note(note_id)
    assert await _removed_at(db_sessionmaker, "notes", "id", note_id) is not None

    await upsert.sync_note(client, note_id)

    assert await _removed_at(db_sessionmaker, "notes", "id", note_id) is None


async def test_sync_buyer_role_clears_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Test Org"))
        await session.commit()

    entry = {
        "id": {"entry_id": "entry-reborn"},
        "parent_record_id": {"record_id": org_id},
        "created_at": "2024-01-01T00:00:00Z",
        "entry_values": {"model": [_item(option={"title": "Financial"})]},
    }
    client = _FakeClient({"/lists/buyer_role/entries/entry-reborn": {"data": entry}})
    client.add_entry_pages("buyer_role", [[entry]])

    await upsert.sync_buyer_role(client, "entry-reborn")
    await upsert.delete_buyer_role("entry-reborn")
    assert (
        await _removed_at(db_sessionmaker, "buyer_roles", "legacy_entry_id", "entry-reborn")
        is not None
    )

    await upsert.sync_buyer_role(client, "entry-reborn")

    assert (
        await _removed_at(db_sessionmaker, "buyer_roles", "legacy_entry_id", "entry-reborn") is None
    )


async def test_sync_seller_role_clears_removed_at(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    org_id = f"test-org-{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        session.add(Organization(attio_id=org_id, name="Test Org"))
        await session.commit()

    entry = {
        "id": {"entry_id": "entry-reborn"},
        "parent_record_id": {"record_id": org_id},
        "created_at": "2024-01-01T00:00:00Z",
        "entry_values": {"outreach_tier": [_item(option={"title": "Tier 1"})]},
    }
    client = _FakeClient({"/lists/seller_role/entries/entry-reborn": {"data": entry}})
    client.add_entry_pages("seller_role", [[entry]])

    await upsert.sync_seller_role(client, "entry-reborn")
    await upsert.delete_seller_role("entry-reborn")
    assert (
        await _removed_at(db_sessionmaker, "seller_roles", "legacy_entry_id", "entry-reborn")
        is not None
    )

    await upsert.sync_seller_role(client, "entry-reborn")

    assert (
        await _removed_at(db_sessionmaker, "seller_roles", "legacy_entry_id", "entry-reborn")
        is None
    )
