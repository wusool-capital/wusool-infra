"""Resolves which Attio record/entry a write actually targets, and issues
that write. `organizations` writes go straight to a record by ID (its
Postgres `attio_id` *is* the Attio record ID). `seller_role`/`buyer_role`
writes target a list *entry*, whose ID Postgres never stores — resolved live
by paging through the list's entries and matching `parent_record_id`,
exactly like this codebase's own `backfill-seller-intake-source.ps1`
(`Get-ParentRecordId`) already does. No server-side `parent_record_id`
filter is used — that script doesn't use one either, and this repo has no
verified precedent for that filter's syntax; paging through ~200-400 total
role entries once per edit is cheap at this scale.

`create_organization`/`create_role_entry` (for `/add-seller`/`/add-buyer`)
use the exact request/response shapes `workflows/crm-sync/scripts/_internal/
objects.ps1`/`lists.ps1` already use live against this same Attio instance —
`POST .../records` returns the new id at `data.id.record_id`
(`objects.ps1`'s own `Id` helper, line ~877); `POST .../entries` requires
both `parent_record_id` and `parent_object` in the body and returns the new
id at `data.id.entry_id` (`lists.ps1`, e.g. line ~984) — not inferred from
docs alone.
"""

from ddl_commands.shared.attio.client import AttioClient

_PAGE_SIZE = 500


class OrgRecordNotFoundError(Exception):
    pass


class RoleEntryNotFoundError(Exception):
    pass


def _entry_parent_record_id(entry: dict) -> str | None:
    parent = entry.get("parent_record_id")
    if isinstance(parent, dict):
        return parent.get("record_id")
    return parent


async def resolve_role_entry_id(client: AttioClient, list_slug: str, org_attio_id: str) -> str:
    offset = 0
    while True:
        response = await client.post(
            f"/lists/{list_slug}/entries/query", {"limit": _PAGE_SIZE, "offset": offset}
        )
        page = response.get("data", [])
        for entry in page:
            if _entry_parent_record_id(entry) == org_attio_id:
                entry_id = entry.get("id", {})
                return entry_id["entry_id"] if isinstance(entry_id, dict) else entry_id
        if len(page) < _PAGE_SIZE:
            break
        offset += _PAGE_SIZE
    raise RoleEntryNotFoundError(
        f"No {list_slug} entry found in Attio for organization {org_attio_id}"
    )


async def patch_organization(client: AttioClient, attio_id: str, values: dict) -> None:
    """`values` maps attribute slug -> Attio's own per-attribute write shape
    (already serialized by the caller via `money.py`/`dates.py`/option
    lookups) — this function issues the write, it doesn't shape it.
    """
    await client.patch(f"/objects/organizations/records/{attio_id}", {"data": {"values": values}})


async def patch_role_entry(
    client: AttioClient, list_slug: str, entry_id: str, entry_values: dict
) -> None:
    await client.patch(
        f"/lists/{list_slug}/entries/{entry_id}", {"data": {"entry_values": entry_values}}
    )


async def create_organization(client: AttioClient, values: dict) -> str:
    """`values` is already Attio's own per-attribute write shape (see
    `write_payload.build_attio_values`), same as `patch_organization` — the
    only difference from an edit is this is a `POST` with no existing
    `attio_id` to target, and the new one comes back in the response.
    """
    response = await client.post("/objects/organizations/records", {"data": {"values": values}})
    return response["data"]["id"]["record_id"]


async def create_role_entry(
    client: AttioClient, list_slug: str, org_attio_id: str, entry_values: dict
) -> str:
    # Every entry created here is, by definition, the only one this bot knows
    # of for this org — `is_active: True` is what the dedup reconciliation
    # (`attio_sync/upsert.py::_reconcile_active_entry`) reads to decide which
    # sibling entry wins, so a freshly created entry has to assert it rather
    # than sit `null` until that reconciliation happens to run.
    response = await client.post(
        f"/lists/{list_slug}/entries",
        {
            "data": {
                "parent_record_id": org_attio_id,
                "parent_object": "organizations",
                "entry_values": {**entry_values, "is_active": True},
            }
        },
    )
    return response["data"]["id"]["entry_id"]
