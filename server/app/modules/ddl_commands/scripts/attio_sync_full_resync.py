"""Nightly safety-net: a full page-through resync of DEV Attio into
Postgres. Complements, not replaces, the real-time webhook — catches
anything a missed delivery, an out-of-order race, or a paused webhook left
inconsistent. Scheduled by `.github/workflows/nightly-attio-sync.yml`.

Unlike the webhook path (one record fetched by id at a time), this reuses
the record/entry data already in hand from its own bulk page-through, and
writes each page as one batched `INSERT ... ON CONFLICT`
(`upsert.upsert_batch_with_retry`) instead of one commit per row.

Entity *types* stay strictly sequential — users, then organizations, then
people/deals, then buyer_role/seller_role — because
`buyer_roles`/`seller_roles.org_attio_id` are hard, unguarded FKs into
`organizations` (unlike the softer-guarded `owner_attio_id`/etc., resolved
here against ids queried fresh after each prior type commits).

`buyer_role`/`seller_role` entries are reconciled once per organization,
not once per raw entry (`_reconcile_active_entry` already fixes every
duplicate for an org regardless of which one triggered it). Every entry
still gets its own Postgres row, though — `org_attio_id` lost its
uniqueness in the 2026-08-28 pluralization, so reconciliation only decides
which entry Attio flags active, not which one Postgres keeps.

After each entity type, a row-count check and a content check (comparing
each batch's `RETURNING` result against what was intended) run against data
from this same pass, at no extra Attio-call cost. Neither can catch a bug
in the field-mapping layer itself, since both sides of the comparison would
agree while both are wrong — see the plan doc for that known gap.
"""

import asyncio
import logging
import resource
import time
from collections.abc import AsyncIterator, Callable

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from app.models import BuyerRole, Deal, Organization, Person, SellerRole
from app.modules.attio import AttioClient, AttioClientProtocol
from app.modules.attio.providers.attio.retry import post_with_retry
from app.modules.ddl_commands.config import get_settings
from app.modules.ddl_commands.persistence import attio_sync as upsert
from app.modules.ddl_commands.persistence.database import get_sessionmaker, import_all_models
from app.modules.utilities.domain.logging import configure_logging

_logger = logging.getLogger("app.modules.ddl_commands.attio_sync.full_resync")

_PAGE_SIZE: int = 500
# Bounded well under the DB engine's default pool ceiling (pool_size=5 +
# max_overflow=10 = 15, shared/database/session.py) -- each concurrent
# batch/reconciliation task holds its own session.
_MAX_CONCURRENT = 5

_COUNT_QUERY = {
    "organizations": text("SELECT count(*) FROM organizations WHERE removed_at IS NULL"),
    "person": text("SELECT count(*) FROM person WHERE removed_at IS NULL"),
    "deals": text("SELECT count(*) FROM deals"),
    "buyer_roles": text("SELECT count(*) FROM buyer_roles"),
    "seller_roles": text("SELECT count(*) FROM seller_roles"),
}
_ID_QUERY = {
    "organizations": text("SELECT attio_id FROM organizations"),
    "person": text("SELECT attio_id FROM person"),
    "users": text("SELECT attio_id FROM users"),
}


def _rss_mb() -> float:
    """Return the process's maximum resident set size in MiB on Linux."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def _page_through(client: AttioClientProtocol, path: str) -> AsyncIterator[list[dict]]:
    # Pagination is strictly serial (offset-based, each page awaited before
    # the next is requested), so this is the term most likely to dominate a
    # slow run.
    offset = 0
    pages = 0
    records = 0
    started = time.monotonic()
    while True:
        response = await post_with_retry(client, path, {"limit": _PAGE_SIZE, "offset": offset})
        page = response.get("data", [])
        pages += 1
        records += len(page)
        _logger.info(
            "full resync: fetched %s page %d — %d records so far, rss=%.1fMiB",
            path,
            pages,
            records,
            _rss_mb(),
        )
        yield page
        if len(page) < _PAGE_SIZE:
            _logger.info(
                "full resync: fetched %s — %d records over %d pages in %.1fs",
                path,
                records,
                pages,
                time.monotonic() - started,
            )
            return
        offset += _PAGE_SIZE


async def _iter_source_pages(source: AsyncIterator[list[dict]]) -> AsyncIterator[list[dict]]:
    async for page in source:
        yield page


async def _collect_pages(
    source: AsyncIterator[list[dict]],
) -> list[dict]:
    records: list[dict] = []
    async for page in _iter_source_pages(source):
        records.extend(page)
    return records


async def _safe_fetch(source: AsyncIterator[list[dict]], label: str) -> list[dict] | None:
    """Wraps one entity type's page-through so a listing failure (Attio 500,
    exhausted retries, malformed page) can't take down the others fetched
    alongside it -- every entity type gets its own chance to sync tonight
    regardless of what happens to its siblings."""
    try:
        return await _collect_pages(source)
    except Exception:
        _logger.error("full resync: failed to list %s records", label, exc_info=True)
        return None


async def _sync_streaming_entity(
    client: AttioClientProtocol,
    model: upsert.SyncModel,
    table: str,
    path: str,
    mapper: Callable[[dict], dict],
) -> tuple[int, int]:
    """Map and write one Attio page at a time, retaining no full listing."""
    total_ok = total_failed = total_records = 0
    try:
        async for page in _iter_source_pages(_page_through(client, path)):
            rows = [mapper(record) for record in page]
            if not rows:
                continue
            ok, failed, returned = await _write_batches_concurrently(model, rows)
            conflict_col = upsert._CONFLICT_COL[model]
            mismatches = [
                key
                for key, intended in ((r[conflict_col], r["raw_attio"]) for r in rows)
                if key in returned and returned[key] != intended
            ]
            total_ok += ok
            total_failed += failed + bool(mismatches)
            total_records += len(rows)
            if mismatches:
                _logger.error("full resync: %s content mismatch for keys: %s", table, mismatches)
        actual_count = await _count(table)
        if actual_count != total_records:
            _logger.error(
                "full resync: %s count mismatch: expected %d, found %d",
                table,
                total_records,
                actual_count,
            )
            total_failed += 1
        else:
            _logger.info("full resync: %s count check passed (%d)", table, actual_count)
    except Exception:
        _logger.error("full resync: failed to sync %s", table, exc_info=True)
        total_failed += 1
    return total_ok, total_failed


async def _existing_ids(table: str) -> set[str]:
    async with get_sessionmaker()() as session:
        rows = await session.execute(_ID_QUERY[table])
        return {r[0] for r in rows}


async def _count(table: str) -> int:
    async with get_sessionmaker()() as session:
        return (await session.execute(_COUNT_QUERY[table])).scalar_one()


def _chunk[T](items: list[T], size: int) -> list[list[T]]:
    return [items[i : i + size] for i in range(0, len(items), size)]


def _can_run_db_tasks_concurrently() -> bool:
    """Serialize tasks for connection-bound rollback fixtures; pool-backed
    production engines remain concurrent."""
    return not isinstance(get_sessionmaker().kw.get("bind"), AsyncConnection)


async def _write_batches_concurrently(
    model: upsert.SyncModel, rows: list[dict]
) -> tuple[int, int, dict]:
    """Batches `rows` into pages and writes them concurrently (bounded) --
    pages are disjoint by conflict key, built from one bulk fetch, so
    concurrent writes to the same table can't race each other. Returns
    aggregated `(ok, failed, returned_by_key)` across every page —
    `returned_by_key` only covers rows written via the batch path (not the
    per-row fallback), for the content-consistency check."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    pages = _chunk(rows, _PAGE_SIZE)

    async def _write_one(page: list[dict], label: str) -> tuple[int, int, dict[str, dict]]:
        async with semaphore:
            return await upsert.upsert_batch_with_retry(model, page, page_label=label)

    writes = [_write_one(page, f"page {i + 1}/{len(pages)}") for i, page in enumerate(pages)]
    results = (
        await asyncio.gather(*writes)
        if _can_run_db_tasks_concurrently()
        else [await write for write in writes]
    )
    ok = sum(r[0] for r in results)
    failed = sum(r[1] for r in results)
    returned: dict = {}
    for r in results:
        returned.update(r[2])
    return ok, failed, returned


async def _write_and_verify(
    model: upsert.SyncModel, table: str, rows: list[dict], expected_count: int
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
    client: AttioClientProtocol,
    list_slug: str,
    entries: list[dict],
    build_params: Callable[[str, dict, bool], dict],
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
            return [build_params(org_id, entry, i == 0) for i, entry in enumerate(reconciled)]
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


async def _sync_notes_full(client: AttioClientProtocol, note_slug: str) -> tuple[int, int]:
    """Plain per-row loop, not the batched `_upsert_batch` path: `notes` has
    no `raw_attio` column (unlike every other table here), so it can't share
    that machinery's content-comparison/RETURNING contract. Note volume is
    much smaller than organizations/deals, so this doesn't need the same
    performance work."""
    try:
        records = await _collect_pages(_page_through(client, f"/objects/{note_slug}/records/query"))
    except Exception:
        _logger.error("full resync: failed to list note records", exc_info=True)
        return 0, 1
    ok = failed = 0
    async with get_sessionmaker()() as session:
        for record in records:
            try:
                await session.execute(upsert._NOTE_UPSERT, upsert._note_params(record))
                ok += 1
            except Exception:
                _logger.error(
                    "full resync: failed to upsert note %s",
                    upsert.v.record_id(record),
                    exc_info=True,
                )
                failed += 1
        await session.commit()
    _logger.info("full resync: note — synced=%d failed=%d", ok, failed)
    return ok, failed


async def run() -> None:
    import_all_models()
    client = AttioClient(get_settings().attio_api_key)
    try:
        await _run(client)
    finally:
        await client.aclose()


async def _run(client: AttioClientProtocol) -> None:
    run_started = time.monotonic()
    settings = get_settings()
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

    summary["organizations"] = await _sync_streaming_entity(
        client,
        Organization,
        "organizations",
        "/objects/organizations/records/query",
        lambda r: dict(upsert._organization_batch_params(r, user_ids)),
    )
    org_ids = await _existing_ids("organizations")

    # People and deals have no hard foreign-key dependency on each other, so
    # stream both concurrently after organizations are available. Each stream
    # still retains at most one page, keeping memory bounded on the micro host.
    person_ids = await _existing_ids("person")
    person_task = _sync_streaming_entity(
        client,
        Person,
        "person",
        "/objects/person/records/query",
        lambda r: dict(upsert._person_batch_params(r, org_ids, user_ids)),
    )
    deal_task = _sync_streaming_entity(
        client,
        Deal,
        "deals",
        f"/objects/{settings.attio_deal_object_slug}/records/query",
        lambda r: dict(upsert._deal_batch_params(r, org_ids, person_ids, user_ids)),
    )
    if _can_run_db_tasks_concurrently():
        person_result, deal_result = await asyncio.gather(person_task, deal_task)
    else:
        person_result = await person_task
        deal_result = await deal_task
    summary["person"] = person_result
    summary["deals"] = deal_result

    # Roles stay collected because reconciliation needs sibling entries across
    # page boundaries; this list is deliberately small in DEV.
    buyer_entries, seller_entries = await asyncio.gather(
        _safe_fetch(_page_through(client, "/lists/buyer_role/entries/query"), "buyer_role"),
        _safe_fetch(_page_through(client, "/lists/seller_role/entries/query"), "seller_role"),
    )

    if buyer_entries is None:
        summary["buyer_role"] = (0, 1)
    else:
        rows, reconcile_failed = await _reconcile_roles(
            client,
            "buyer_role",
            buyer_entries,
            lambda org_id, entry, is_active: dict(
                upsert._buyer_role_batch_params(org_id, entry, is_active, person_ids)
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
            lambda org_id, entry, is_active: dict(
                upsert._seller_role_params(org_id, entry, is_active)
            ),
        )
        ok, write_failed = await _write_and_verify(SellerRole, "seller_roles", rows, len(rows))
        summary["seller_role"] = (ok, reconcile_failed + write_failed)

    # The unified "note" object only exists in SOURCE Attio today (prod) --
    # DEV Attio has no such object yet, so dev leaves ATTIO_NOTE_OBJECT_SLUG
    # unset and this entity is skipped entirely rather than logging a nightly
    # "failed to list note records" error for an object that isn't there.
    if settings.attio_note_object_slug:
        summary["note"] = await _sync_notes_full(client, settings.attio_note_object_slug)

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
    configure_logging(get_settings().log_level)
    asyncio.run(run())


if __name__ == "__main__":
    main()
