"""Nightly safety-net: a full page-through resync of DEV Attio into
Postgres. Complements, not replaces, the real-time webhook — catches
anything a missed delivery, an out-of-order race, or a paused webhook (see
the migration-pause runbook handed over separately) left inconsistent.

Run via `python -m ddl_commands.modules.attio_sync.full_resync`, invoked on
a schedule by `.github/workflows/nightly-attio-sync.yml` — the same
SSM-into-the-toolkit-container pattern `_deploy.yml` already uses for
`alembic upgrade head` (RDS is private; the toolkit EC2 instance is the only
thing with a network path to it).

Unlike the webhook path (`upsert.py`'s `sync_*` functions, which each fetch
one record by id), this reuses the full record/entry data it already has
from its own bulk page-through directly -- no per-record re-fetch. Writes
are batched (`upsert.upsert_batch_with_retry`, one multi-row `INSERT ... ON
CONFLICT` per page) instead of one commit per row, and pages of the same
entity type write concurrently (bounded) since they're disjoint by conflict
key. Entity *types* stay strictly sequential -- users, then organizations,
then people/deals, then buyer_role/seller_role -- because
`buyer_roles.org_attio_id`/`seller_roles.org_attio_id` are hard, unguarded
foreign keys into `organizations` (unlike `owner_attio_id`/
`company_attio_id`/etc., which are soft-guarded and resolved here against
id sets queried fresh from Postgres after each prior entity type commits).

`buyer_role`/`seller_role` entries are reconciled per organization
(`upsert.group_entries_by_org` + `upsert._reconcile_active_entry`, run
concurrently across orgs, bounded) -- `_reconcile_active_entry` already
re-corrects every duplicate for that org regardless of which one triggered
it, so reconciling once per org (not once per raw entry) gets the same
result without redoing that work N times. Every entry still gets its own
Postgres row, though, not just the winner: `buyer_roles`/`seller_roles.
org_attio_id` lost its uniqueness in the 2026-08-28 pluralization (Postgres
now mirrors every DEV Attio entry, `legacy_entry_id` the row key,
`is_active` telling winner from duplicate) -- reconciliation only decides
which entry Attio itself should flag active, not which one Postgres keeps.

After each entity type's writes, two consistency checks run against data
already in memory from this same pass -- no extra Attio calls: a row-count
check (`sync-postgres.ps1`'s existing convention, reused as-is) and a
content check comparing each batch's `RETURNING` result against what was
intended to be written. Neither can catch a bug in the field-mapping layer
itself (both sides of that comparison would agree while both are wrong) --
that would require an independent re-fetch from Attio, which is exactly the
per-record cost this file avoids. See the module's PR description / plan
doc for the tradeoff and a proposed periodic-spot-check follow-up.
"""

import asyncio
import logging
import time

from sqlalchemy import text
from wusool_db.models import BuyerRole, Deal, Organization, Person, SellerRole

from ddl_commands.config import get_settings
from ddl_commands.modules.attio_sync import upsert
from ddl_commands.modules.attio_sync.retry import post_with_retry
from ddl_commands.shared.attio.client import AttioClient
from ddl_commands.shared.database import import_all_models
from ddl_commands.shared.database.session import get_sessionmaker

_logger = logging.getLogger("ddl_commands.attio_sync.full_resync")

_PAGE_SIZE = 500
# Bounded well under the DB engine's default pool ceiling (pool_size=5 +
# max_overflow=10 = 15, shared/database/session.py) -- each concurrent
# batch/reconciliation task holds its own session.
_MAX_CONCURRENT = 5

_COUNT_QUERY = {
    "organizations": text("SELECT count(*) FROM organizations WHERE removed_at IS NULL"),
    "people": text("SELECT count(*) FROM people WHERE removed_at IS NULL"),
    "deals": text("SELECT count(*) FROM deals"),
    "buyer_roles": text("SELECT count(*) FROM buyer_roles"),
    "seller_roles": text("SELECT count(*) FROM seller_roles"),
}
_ID_QUERY = {
    "organizations": text("SELECT attio_id FROM organizations"),
    "people": text("SELECT attio_id FROM people"),
    "users": text("SELECT attio_id FROM users"),
}


async def _page_through(client: AttioClient, path: str) -> list[dict]:
    # Timed per stream, not just for the fetch phase as a whole: all five
    # page-throughs run under one `asyncio.gather` below, so the phase-level
    # duration only ever reports the slowest one without saying which it
    # was. Pagination here is strictly serial (offset-based, each page
    # awaited before the next is requested), so this is the term most likely
    # to dominate a slow run.
    items: list[dict] = []
    offset = 0
    pages = 0
    started = time.monotonic()
    while True:
        response = await post_with_retry(client, path, {"limit": _PAGE_SIZE, "offset": offset})
        page = response.get("data", [])
        items.extend(page)
        pages += 1
        if len(page) < _PAGE_SIZE:
            _logger.info(
                "full resync: fetched %s — %d records over %d pages in %.1fs",
                path,
                len(items),
                pages,
                time.monotonic() - started,
            )
            return items
        offset += _PAGE_SIZE


async def _safe_fetch(coro, label: str) -> list[dict] | None:
    """Wraps one entity type's page-through so a listing failure (Attio 500,
    exhausted retries, malformed page) can't take down the others fetched
    alongside it -- every entity type gets its own chance to sync tonight
    regardless of what happens to its siblings."""
    try:
        return await coro
    except Exception:
        _logger.error("full resync: failed to list %s records", label, exc_info=True)
        return None


async def _existing_ids(table: str) -> set[str]:
    async with get_sessionmaker()() as session:
        rows = await session.execute(_ID_QUERY[table])
        return {r[0] for r in rows}


async def _count(table: str) -> int:
    async with get_sessionmaker()() as session:
        return (await session.execute(_COUNT_QUERY[table])).scalar_one()


def _chunk(items: list, size: int) -> list[list]:
    return [items[i : i + size] for i in range(0, len(items), size)]


async def _write_batches_concurrently(model, rows: list[dict]) -> tuple[int, int, dict]:
    """Batches `rows` into pages and writes them concurrently (bounded) --
    pages are disjoint by conflict key, built from one bulk fetch, so
    concurrent writes to the same table can't race each other. Returns
    aggregated `(ok, failed, returned_by_key)` across every page —
    `returned_by_key` only covers rows written via the batch path (not the
    per-row fallback), for the content-consistency check."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    pages = _chunk(rows, _PAGE_SIZE)

    async def _write_one(page: list[dict], label: str):
        async with semaphore:
            return await upsert.upsert_batch_with_retry(model, page, page_label=label)

    results = await asyncio.gather(
        *(_write_one(page, f"page {i + 1}/{len(pages)}") for i, page in enumerate(pages))
    )
    ok = sum(r[0] for r in results)
    failed = sum(r[1] for r in results)
    returned: dict = {}
    for r in results:
        returned.update(r[2])
    return ok, failed, returned


async def _write_and_verify(
    model, table: str, rows: list[dict], expected_count: int
) -> tuple[int, int]:
    started = time.monotonic()
    ok, failed, returned = await _write_batches_concurrently(model, rows)
    _logger.info(
        "full resync: %s changed=%d unchanged=%d write_duration=%.1fs",
        table,
        len(returned),
        len(rows) - len(returned),
        time.monotonic() - started,
    )
    conflict_col = upsert._CONFLICT_COL[model]
    intended_by_key = {r[conflict_col]: r["raw_attio"] for r in rows}
    mismatches = [
        key
        for key, intended in intended_by_key.items()
        if key in returned and returned[key] != intended
    ]
    if mismatches:
        _logger.error(
            "full resync: %s content mismatch after write for keys: %s", table, mismatches
        )
        failed += 1
    actual_count = await _count(table)
    if actual_count != expected_count:
        _logger.error(
            "full resync: %s count mismatch: expected %d, found %d",
            table,
            expected_count,
            actual_count,
        )
        failed += 1
    else:
        _logger.info("full resync: %s count check passed (%d)", table, actual_count)
    return ok, failed


async def _reconcile_roles(
    client: AttioClient, list_slug: str, entries: list[dict], build_params
) -> tuple[list[dict], int]:
    """Groups `entries` by org (one pass, already in hand) and reconciles
    each org's duplicates concurrently (bounded) -- each org's sibling set
    and is_active PATCH-back is independent of every other org's. Postgres
    mirrors every DEV Attio entry now, one row each keyed by legacy_entry_id
    (see BuyerRole/SellerRole's 2026-08-28 pluralization), so this returns
    one row per *entry*, not per org -- `build_params(org_id, entry,
    is_active)` is called once per sibling, `is_active` set explicitly from
    its position in the reconciled list (winner=True, every loser=False).
    Second return value is a count of orgs whose reconciliation failed
    entirely (every one of that org's entries lost, not just one row)."""
    started = time.monotonic()
    by_org = upsert.group_entries_by_org(entries)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _reconcile_one(org_id: str, siblings: list[dict]) -> list[dict] | None:
        try:
            async with semaphore:
                reconciled = await upsert._reconcile_active_entry(client, list_slug, siblings)
            return [
                build_params(org_id, entry, i == 0) for i, entry in enumerate(reconciled)
            ]
        except Exception:
            _logger.error(
                "full resync: failed to reconcile %s org %s", list_slug, org_id, exc_info=True
            )
            return None

    results = await asyncio.gather(
        *(_reconcile_one(org_id, siblings) for org_id, siblings in by_org.items())
    )
    rows = [row for group in results if group is not None for row in group]
    failed_orgs = sum(1 for group in results if group is None)
    _logger.info(
        "full resync: %s reconciled %d/%d orgs (%d entries) in %.1fs",
        list_slug,
        len(results) - failed_orgs,
        len(results),
        len(rows),
        time.monotonic() - started,
    )
    return rows, failed_orgs


async def run() -> None:
    import_all_models()
    client = AttioClient(get_settings().attio_api_key)
    try:
        await _run(client)
    finally:
        await client.aclose()


async def _run(client: AttioClient) -> None:
    run_started = time.monotonic()
    summary: dict[str, tuple[int, int]] = {}

    users_synced = 0
    try:
        users_synced = await upsert.sync_all_users(client)
    except Exception:
        _logger.error("full resync: failed to sync users", exc_info=True)
        summary["users"] = (0, 1)
    else:
        summary["users"] = (users_synced, 0)
    _logger.info("full resync: users — synced=%d", users_synced)
    user_ids = await _existing_ids("users")

    # Fetch phase -- pure reads, safe to run concurrently.
    fetch_started = time.monotonic()
    org_records, person_records, deal_records, buyer_entries, seller_entries = await asyncio.gather(
        _safe_fetch(
            _page_through(client, "/objects/organizations/records/query"), "organizations"
        ),
        _safe_fetch(_page_through(client, "/objects/person/records/query"), "person"),
        _safe_fetch(_page_through(client, "/objects/deals/records/query"), "deals"),
        _safe_fetch(_page_through(client, "/lists/buyer_role/entries/query"), "buyer_role"),
        _safe_fetch(_page_through(client, "/lists/seller_role/entries/query"), "seller_role"),
    )
    _logger.info(
        "full resync: fetch phase complete in %.1fs — organizations=%s person=%s deals=%s "
        "buyer_role=%s seller_role=%s",
        time.monotonic() - fetch_started,
        "FAILED" if org_records is None else len(org_records),
        "FAILED" if person_records is None else len(person_records),
        "FAILED" if deal_records is None else len(deal_records),
        "FAILED" if buyer_entries is None else len(buyer_entries),
        "FAILED" if seller_entries is None else len(seller_entries),
    )

    # organizations
    if org_records is None:
        summary["organizations"] = (0, 1)
    else:
        rows = [upsert._organization_batch_params(r, user_ids) for r in org_records]
        summary["organizations"] = await _write_and_verify(
            Organization, "organizations", rows, len(org_records)
        )
    org_ids = await _existing_ids("organizations")

    # people
    if person_records is None:
        summary["person"] = (0, 1)
    else:
        rows = [upsert._person_batch_params(r, org_ids, user_ids) for r in person_records]
        summary["person"] = await _write_and_verify(Person, "people", rows, len(person_records))
    person_ids = await _existing_ids("people")

    # deals
    if deal_records is None:
        summary["deals"] = (0, 1)
    else:
        rows = [
            upsert._deal_batch_params(r, org_ids, person_ids, user_ids) for r in deal_records
        ]
        summary["deals"] = await _write_and_verify(Deal, "deals", rows, len(deal_records))

    # buyer_role / seller_role -- reconcile duplicates per org concurrently
    # (still one is_active PATCH-back per org), then one batched write for
    # every entry (not just the winner -- see BuyerRole/SellerRole's
    # 2026-08-28 pluralization: Postgres mirrors every DEV Attio entry now).
    if buyer_entries is None:
        summary["buyer_role"] = (0, 1)
    else:
        rows, reconcile_failed = await _reconcile_roles(
            client,
            "buyer_role",
            buyer_entries,
            lambda org_id, entry, is_active: upsert._buyer_role_batch_params(
                org_id, entry, is_active, person_ids
            ),
        )
        ok, write_failed = await _write_and_verify(BuyerRole, "buyer_roles", rows, len(rows))
        summary["buyer_role"] = (ok, reconcile_failed + write_failed)

    if seller_entries is None:
        summary["seller_role"] = (0, 1)
    else:
        rows, reconcile_failed = await _reconcile_roles(
            client,
            "seller_role",
            seller_entries,
            lambda org_id, entry, is_active: upsert._seller_role_params(org_id, entry, is_active),
        )
        ok, write_failed = await _write_and_verify(SellerRole, "seller_roles", rows, len(rows))
        summary["seller_role"] = (ok, reconcile_failed + write_failed)

    total_ok = sum(ok for ok, _ in summary.values())
    total_failed = sum(failed for _, failed in summary.values())
    for slug, (ok, failed) in summary.items():
        _logger.info("full resync: %-14s synced=%-5d failed=%d", slug, ok, failed)
    _logger.info(
        "full resync complete: synced=%d failed=%d duration=%.1fs",
        total_ok,
        total_failed,
        time.monotonic() - run_started,
    )

    if total_failed:
        # Non-zero exit code — the SSM/GH Actions caller must see this as failed.
        raise SystemExit(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
