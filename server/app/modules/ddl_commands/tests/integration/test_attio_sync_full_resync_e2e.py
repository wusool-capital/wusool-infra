"""End-to-end exercise of `full_resync._run()` against a real (rolled-back)
transaction — proves the whole rewritten pipeline (parallel fetch, batched
writes, cross-entity FK resolution, per-org reconciliation, consistency
checks) works together, not just each piece in isolation. Skips cleanly
(via `db_sessionmaker`, see conftest.py) when no SSM tunnel is open.
"""

import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ddl_commands.persistence import attio_sync as upsert
from app.modules.ddl_commands.scripts import attio_sync_full_resync as full_resync


def _item(**kwargs) -> dict:
    return {"active_until": None, **kwargs}


def _org(oid: str, name: str) -> dict:
    return {"id": {"record_id": oid}, "values": {"name": [_item(value=name)]}}


def _person(pid: str, name: str, company_id: str) -> dict:
    return {
        "id": {"record_id": pid},
        "values": {
            "name": [_item(value=name)],
            "company": [_item(target_record_id=company_id)],
        },
    }


def _deal(did: str, name: str, buyer_id: str, seller_id: str) -> dict:
    return {
        "id": {"record_id": did},
        "values": {
            "name": [_item(value=name)],
            "buyer_id": [_item(target_record_id=buyer_id)],
            "seller_id": [_item(target_record_id=seller_id)],
        },
    }


def _role_entry(entry_id: str, org_id: str, created_at: str) -> dict:
    return {
        "id": {"entry_id": entry_id},
        "parent_record_id": {"record_id": org_id},
        "created_at": created_at,
        "entry_values": {},
    }


class _FakeClient:
    """Serves canned responses for every path `full_resync._run()` touches:
    `/workspace_members` (GET), each entity type's `/query` pagination
    (POST), and buyer/seller-role `is_active` corrections (PATCH)."""

    def __init__(self, query_pages: dict[str, list[dict]], members: list[dict]) -> None:
        self._query_pages = query_pages
        self._members = members
        self.patch_calls: list[tuple[str, dict]] = []

    async def get(self, path: str) -> dict:
        assert path == "/workspace_members"
        return {"data": self._members}

    async def post(self, path: str, json_body: dict) -> dict:
        offset = json_body["offset"]
        limit = json_body["limit"]
        page = self._query_pages.get(path, [])[offset : offset + limit]
        return {"data": page}

    async def patch(self, path: str, json_body: dict) -> dict:
        self.patch_calls.append((path, json_body))
        return {}

    async def aclose(self) -> None:
        pass


async def test_full_resync_run_end_to_end(
    monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]
) -> None:
    monkeypatch.setattr(upsert, "get_sessionmaker", lambda: db_sessionmaker)
    monkeypatch.setattr(full_resync, "get_sessionmaker", lambda: db_sessionmaker)
    monkeypatch.setattr(full_resync, "import_all_models", lambda: None)

    org_1, org_2 = f"test-org-{uuid.uuid4()}", f"test-org-{uuid.uuid4()}"
    person_1 = f"test-person-{uuid.uuid4()}"
    deal_1 = f"test-deal-{uuid.uuid4()}"

    client = _FakeClient(
        query_pages={
            "/objects/organizations/records/query": [
                _org(org_1, "Buyer Co"),
                _org(org_2, "Seller Co"),
            ],
            "/objects/person/records/query": [_person(person_1, "Jane Doe", org_1)],
            "/objects/deals/records/query": [_deal(deal_1, "Test Deal", org_1, org_2)],
            "/lists/buyer_role/entries/query": [
                _role_entry("buyer-entry-1", org_1, "2024-01-01T00:00:00Z")
            ],
            "/lists/seller_role/entries/query": [
                _role_entry("seller-entry-1", org_2, "2024-01-01T00:00:00Z")
            ],
        },
        members=[{"id": {"workspace_member_id": "member-1"}, "name": "Alice"}],
    )

    monkeypatch.setattr(full_resync, "AttioClient", lambda api_key: client)

    await full_resync.run()

    async with db_sessionmaker() as session:
        org_names = {
            row[0]: row[1]
            for row in (
                await session.execute(
                    text(
                        "SELECT attio_id, name FROM organizations "
                        "WHERE attio_id = ANY(:ids)"
                    ),
                    {"ids": [org_1, org_2]},
                )
            ).all()
        }
        person_row = (
            await session.execute(
                text("SELECT name, company_attio_id FROM person WHERE attio_id = :id"),
                {"id": person_1},
            )
        ).one()
        deal_row = (
            await session.execute(
                text(
                    "SELECT buyer_organization_attio_id, seller_organization_attio_id "
                    "FROM deals WHERE attio_id = :id"
                ),
                {"id": deal_1},
            )
        ).one()
        buyer_role_org = (
            await session.execute(
                text("SELECT org_attio_id FROM buyer_roles WHERE org_attio_id = :id"),
                {"id": org_1},
            )
        ).scalar_one()
        seller_role_org = (
            await session.execute(
                text("SELECT org_attio_id FROM seller_roles WHERE org_attio_id = :id"),
                {"id": org_2},
            )
        ).scalar_one()

    assert org_names == {org_1: "Buyer Co", org_2: "Seller Co"}
    # The person's `company` FK resolves to the real org -- proves
    # `_person_batch_params`'s id-set resolution ran after organizations
    # actually committed, not just after they were fetched.
    assert person_row == ("Jane Doe", org_1)
    # Same proof for deals' buyer/seller organization FKs.
    assert deal_row == (org_1, org_2)
    assert buyer_role_org == org_1
    assert seller_role_org == org_2
    # The single buyer_role/seller_role entry had no `is_active` value ->
    # reconciliation should have flipped it to true in Attio.
    assert (
        "/lists/buyer_role/entries/buyer-entry-1",
        {"data": {"entry_values": {"is_active": True}}},
    ) in client.patch_calls
    assert (
        "/lists/seller_role/entries/seller-entry-1",
        {"data": {"entry_values": {"is_active": True}}},
    ) in client.patch_calls
