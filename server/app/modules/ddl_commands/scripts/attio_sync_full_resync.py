"""Nightly safety-net: a full page-through resync of SOURCE Attio into
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
from app.modules.attio import AttioClient, AttioClientProtocol, attio_is_test
from app.modules.attio.config import get_settings as get_attio_settings
from app.modules.attio.domain.records import AttioRecord
from app.modules.attio.providers.attio.retry import post_with_retry
from app.modules.ddl_commands.config import get_settings
from app.modules.ddl_commands.persistence import attio_sync as upsert
from app.modules.ddl_commands.persistence.database import get_sessionmaker, import_all_models
from app.modules.utilities.domain.json_types import JsonObject
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
    "deals": text("SELECT count(*) FROM deals WHERE removed_at IS NULL"),
    "buyer_roles": text("SELECT count(*) FROM buyer_roles WHERE removed_at IS NULL"),
    "seller_roles": text("SELECT count(*) FROM seller_roles WHERE removed_at IS NULL"),
    "notes": text("SELECT count(*) FROM notes WHERE removed_at IS NULL AND attio_id IS NOT NULL"),
}
_ID_QUERY = {
    "organizations": text("SELECT attio_id FROM organizations"),
    "person": text("SELECT attio_id FROM person"),
    "users": text("SELECT attio_id FROM users"),
}


def _rss_mb() -> float:
    """Return the process's maximum resident set size in MiB on Linux."""
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


async def _page_through(client: AttioClientProtocol, path: str) -> AsyncIterator[list[AttioRecord]]:
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


async def _iter_source_pages(
    source: AsyncIterator[list[AttioRecord]],
) -> AsyncIterator[list[AttioRecord]]:
    async for page in source:
        yield page


async def _collect_pages(
    source: AsyncIterator[list[AttioRecord]],
) -> list[AttioRecord]:
    records: list[AttioRecord] = []
    async for page in _iter_source_pages(source):
        records.extend(page)
    return records


async def _safe_fetch(
    source: AsyncIterator[list[AttioRecord]], label: str
) -> list[AttioRecord] | None:
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
    mapper: Callable[[AttioRecord], JsonObject],
    seen_ids: set[str] | None = None,
    verify_count: bool = True,
) -> tuple[int, int]:
    """Map and write one Attio page at a time, retaining no full listing.

    `seen_ids`, when given, accumulates every in-scope record's conflict-column
    value for deletion reconciliation. That is the one thing kept across pages,
    and deliberately so: the largest entity is `person` at ~4.8k ids of ~36
    chars, well under a megabyte, so it does not threaten the bounded-memory
    property the page-at-a-time streaming exists to protect.
    """
    total_ok = total_failed = total_records = 0
    try:
        async for page in _iter_source_pages(_page_through(client, path)):
            in_scope = [record for record in page if upsert.in_scope(record)]
            if len(in_scope) != len(page):
                _logger.info(
                    "full resync: %s skipped %d out-of-scope records",
                    table,
                    len(page) - len(in_scope),
                )
            rows = [mapper(record) for record in in_scope]
            if not rows:
                continue
            ok, failed, returned = await _write_batches_concurrently(model, rows)
            conflict_col = upsert._CONFLICT_COL[model]
            if seen_ids is not None:
                seen_ids.update(r[conflict_col] for r in rows if r.get(conflict_col))
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
        # Skipped when `_reconcile_deletions` follows: before it runs, the live
        # count still includes rows pending deletion, so this would fail the job
        # for a mirror that is about to be correct.
        if verify_count:
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


# The key each table is reconciled on -- the same one the webhook's delete
# handlers match (`persistence/attio_sync.py`), so the nightly and the live
# path cannot disagree about identity. `notes` is deliberately absent: a note
# whose Attio push failed keeps a local `gen_random_uuid()` that no Attio
# record id can equal, and Attio record ids are UUIDs too, so a set difference
# would mark every failed-push meeting summary removed. Notes needs a
# discriminator column before it can join this.
_RECONCILE_KEY = {
    "organizations": "attio_id",
    "person": "attio_id",
    "deals": "attio_id",
    "buyer_roles": "legacy_entry_id",
    "seller_roles": "legacy_entry_id",
    # Keyed on `attio_id`, never `id`. A note the meetings pipeline authored
    # whose Attio push failed keeps a local gen_random_uuid() `id` and a NULL
    # `attio_id`, and `NULL = ANY(...)` is never true -- so such a row can
    # never be selected for stamping. Structural protection, not a special
    # case someone has to remember.
    "notes": "attio_id",
}

# A partial page-through -- an API hiccup halfway -- would otherwise stamp every
# unreturned row as deleted. The zero-fetch guard below only catches a total
# failure, so anything above this share of live rows is treated as implausible
# and reported instead of written. Same shape as
# `scripts/postgres-sync/prod/sync-source-to-prod.ps1`'s own >10% abort.
_MAX_STALE_SHARE = 0.02
_MIN_STALE_ALLOWANCE = 10


async def _reconcile_into(
    summary: dict[str, tuple[int, int]], key: str, table: str, live_ids: set[str]
) -> None:
    """Reconcile and fold any failure into `summary[key]`, so a refusal or a
    post-reconciliation mismatch reaches the job's exit status instead of being
    logged and dropped."""
    ok, failed = summary[key]
    summary[key] = (ok, failed + await _reconcile_deletions(table, live_ids))


async def _reconcile_deletions(table: str, live_ids: set[str]) -> int:
    """Mirror Attio deletions into `removed_at`, returning a failure count.

    Soft delete only -- nothing is physically removed, so a wrong call is
    reversible with `UPDATE <table> SET removed_at = NULL`. That is why this
    can run unattended where the hard `DELETE`s it replaces could not.

    This is also where the mirror is *verified*, deliberately. The row-count
    check used to live in `_sync_streaming_entity`/`_write_and_verify`, which
    run before this -- so a table with pending deletions reported a count
    mismatch and failed the whole job even when reconciliation then handled it
    perfectly (observed 2026-09-15: buyer_roles and seller_roles both
    reconciled cleanly and both still reported failed=1). Counting after the
    write is the only point where the answer means anything.
    """
    key = _RECONCILE_KEY[table]
    if not live_ids:
        # Zero ids is only alarming if there is something to lose. An empty
        # Attio listing alongside an empty table means the two agree -- a fresh
        # environment, or an object genuinely not in use -- and failing the
        # nightly for that would make it permanently red for no reason. Zero
        # ids while rows exist is the dangerous case the guard is for.
        async with get_sessionmaker()() as session:
            live = (
                await session.execute(
                    text(
                        f"SELECT count(*) FROM {table} "  # noqa: S608
                        f"WHERE removed_at IS NULL AND {key} IS NOT NULL"
                    )
                )
            ).scalar_one()
        if live == 0:
            _logger.info("full resync: %s has nothing to reconcile (empty on both sides)", table)
            return 0
        _logger.error(
            "full resync: %s returned zero ids from Attio while %d live rows exist -- "
            "refusing to mark them all removed. Reconciliation skipped for this table.",
            table,
            live,
        )
        return 1

    ids = list(live_ids)
    async with get_sessionmaker()() as session:
        stale = (
            await session.execute(
                text(
                    f"SELECT count(*) FROM {table} "  # noqa: S608 - table from _RECONCILE_KEY
                    f"WHERE removed_at IS NULL AND {key} IS NOT NULL "
                    f"AND NOT ({key} = ANY(:ids))"
                ),
                {"ids": ids},
            )
        ).scalar_one()
        live = (
            await session.execute(
                text(
                    f"SELECT count(*) FROM {table} "  # noqa: S608
                    f"WHERE removed_at IS NULL AND {key} IS NOT NULL"
                )
            )
        ).scalar_one()

        allowance = max(_MIN_STALE_ALLOWANCE, int(live * _MAX_STALE_SHARE))
        if stale > allowance:
            sample = (
                (
                    await session.execute(
                        text(
                            f"SELECT {key} FROM {table} "  # noqa: S608
                            f"WHERE removed_at IS NULL AND {key} IS NOT NULL "
                            f"AND NOT ({key} = ANY(:ids)) LIMIT 10"
                        ),
                        {"ids": ids},
                    )
                )
                .scalars()
                .all()
            )
            _logger.error(
                "full resync: %s would mark %d of %d live rows removed, above the %d "
                "allowance -- refusing. Attio returned %d ids. Sample: %s",
                table,
                stale,
                live,
                allowance,
                len(ids),
                sample,
            )
            # A refusal leaves the mirror knowingly unconverged, so it stays a
            # failure -- silently returning success would hide real drift.
            return 1

        # Counted with SELECTs rather than the UPDATEs' rowcount: the async
        # `Result` does not expose it, and `stale` is already measured above
        # for the guard, so this needs one extra query rather than a cast.
        cleared = (
            await session.execute(
                text(
                    f"SELECT count(*) FROM {table} "  # noqa: S608
                    f"WHERE removed_at IS NOT NULL AND {key} = ANY(:ids)"
                ),
                {"ids": ids},
            )
        ).scalar_one()
        await session.execute(
            text(
                f"UPDATE {table} SET removed_at = now() "  # noqa: S608
                f"WHERE removed_at IS NULL AND {key} IS NOT NULL "
                f"AND NOT ({key} = ANY(:ids))"
            ),
            {"ids": ids},
        )
        await session.execute(
            text(
                f"UPDATE {table} SET removed_at = NULL "  # noqa: S608
                f"WHERE removed_at IS NOT NULL AND {key} = ANY(:ids)"
            ),
            {"ids": ids},
        )
        await session.commit()
        stamped = stale

    if stamped or cleared:
        _logger.warning(
            "full resync: %s reconciled -- %d marked removed, %d restored (%d live in Attio)",
            table,
            stamped,
            cleared,
            len(ids),
        )
    else:
        _logger.info("full resync: %s already mirrors Attio (%d records)", table, len(ids))

    # The mirror assertion, now that reconciliation has run: live rows must
    # equal what Attio returned. A difference here is real divergence, not a
    # deletion waiting to be processed.
    async with get_sessionmaker()() as session:
        final = (
            await session.execute(
                text(
                    f"SELECT count(*) FROM {table} "  # noqa: S608
                    f"WHERE removed_at IS NULL AND {key} IS NOT NULL"
                )
            )
        ).scalar_one()
    if final != len(ids):
        _logger.error(
            "full resync: %s count mismatch after reconciliation: Attio has %d, "
            "Postgres has %d live",
            table,
            len(ids),
            final,
        )
        return 1
    _logger.info("full resync: %s count check passed (%d)", table, final)
    return 0


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
    model: upsert.SyncModel, rows: list[JsonObject]
) -> tuple[int, int, dict[str, JsonObject]]:
    """Batches `rows` into pages and writes them concurrently (bounded) --
    pages are disjoint by conflict key, built from one bulk fetch, so
    concurrent writes to the same table can't race each other. Returns
    aggregated `(ok, failed, returned_by_key)` across every page —
    `returned_by_key` only covers rows written via the batch path (not the
    per-row fallback), for the content-consistency check."""
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)
    pages = _chunk(rows, _PAGE_SIZE)

    async def _write_one(
        page: list[JsonObject], label: str
    ) -> tuple[int, int, dict[str, JsonObject]]:
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
    returned: dict[str, JsonObject] = {}
    for r in results:
        returned.update(r[2])
    return ok, failed, returned


async def _write_and_verify(
    model: upsert.SyncModel,
    table: str,
    rows: list[JsonObject],
    expected_count: int,
    verify_count: bool = True,
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
    # The content-mismatch check above stays here -- it is about write
    # fidelity, not row counts. The row count moves to _reconcile_deletions,
    # which runs after and is the only place the answer is meaningful.
    if verify_count:
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
    entries: list[AttioRecord],
    build_params: Callable[[str, AttioRecord, bool], JsonObject],
) -> tuple[list[JsonObject], int]:
    """Groups `entries` by org (one pass, already in hand) and reconciles
    each org's duplicates concurrently (bounded) -- each org's sibling set
    and is_active PATCH-back is independent of every other org's. Postgres
    mirrors every SOURCE Attio entry now, one row each keyed by legacy_entry_id
    (see BuyerRole/SellerRole's 2026-08-28 pluralization), so this returns
    one row per *entry*, not per org -- `build_params(org_id, entry,
    is_active)` is called once per sibling, `is_active` set explicitly from
    its position in the reconciled list (winner=True, every loser=False).
    Second return value is a count of orgs whose reconciliation failed
    entirely (every one of that org's entries lost, not just one row)."""
    started = time.monotonic()
    by_org = upsert.group_entries_by_org(entries)
    semaphore = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _reconcile_one(org_id: str, siblings: list[AttioRecord]) -> list[JsonObject] | None:
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


async def _sync_notes_full(
    client: AttioClientProtocol, seen_ids: set[str] | None = None
) -> tuple[int, int]:
    """Plain per-row loop, not the batched `_upsert_batch` path: `notes` has
    no `raw_attio` column (unlike every other table here), so it can't share
    that machinery's content-comparison/RETURNING contract. Note volume is
    much smaller than organizations/deals, so this doesn't need the same
    performance work."""
    try:
        fetched = await _collect_pages(_page_through(client, "/objects/note/records/query"))
    except Exception:
        _logger.error("full resync: failed to list note records", exc_info=True)
        return 0, 1
    records = [record for record in fetched if upsert.in_scope(record)]
    if seen_ids is not None:
        seen_ids.update(upsert.v.record_id(r) for r in records if upsert.v.record_id(r))
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
    # Its own client rather than the shared `get_attio_client()`: that one is
    # `lru_cache`d process-wide and this script closes what it opens.
    client = AttioClient(get_attio_settings().api_key)
    try:
        await _run(client)
    finally:
        await client.aclose()


async def _run(client: AttioClientProtocol) -> None:
    # The one place a loud stop beats failing safe. Sync runs only SOURCE ->
    # the prod database; a resync pointed at the dev sandbox would overwrite
    # thousands of rows and wipe the test data devs just created, which is
    # far worse than a skipped night.
    if attio_is_test():
        _logger.error("full resync: refusing to run with ATTIO_IS_TEST=true (prod-only job)")
        raise SystemExit(1)

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

    live_org_ids: set[str] = set()
    summary["organizations"] = await _sync_streaming_entity(
        client,
        Organization,
        "organizations",
        "/objects/organizations/records/query",
        lambda r: dict(upsert._organization_batch_params(r, user_ids)),
        live_org_ids,
        verify_count=False,
    )
    await _reconcile_into(summary, "organizations", "organizations", live_org_ids)
    org_ids = await _existing_ids("organizations")

    # People and deals have no hard foreign-key dependency on each other, so
    # stream both concurrently after organizations are available. Each stream
    # still retains at most one page, keeping memory bounded on the micro host.
    person_ids = await _existing_ids("person")
    live_person_ids: set[str] = set()
    live_deal_ids: set[str] = set()
    person_task = _sync_streaming_entity(
        client,
        Person,
        "person",
        "/objects/person/records/query",
        lambda r: dict(upsert._person_batch_params(r, org_ids, user_ids)),
        live_person_ids,
        verify_count=False,
    )
    deal_task = _sync_streaming_entity(
        client,
        Deal,
        "deals",
        "/objects/deal/records/query",
        lambda r: dict(upsert._deal_batch_params(r, org_ids, person_ids, user_ids)),
        live_deal_ids,
        verify_count=False,
    )
    if _can_run_db_tasks_concurrently():
        person_result, deal_result = await asyncio.gather(person_task, deal_task)
    else:
        person_result = await person_task
        deal_result = await deal_task
    summary["person"] = person_result
    summary["deals"] = deal_result
    # After both streams, so a failed page-through leaves the id set short and
    # trips the guard rather than stamping the difference.
    await _reconcile_into(summary, "person", "person", live_person_ids)
    await _reconcile_into(summary, "deals", "deals", live_deal_ids)

    # Roles stay collected because reconciliation needs sibling entries across
    # page boundaries; this list is deliberately small in DEV.
    buyer_entries, seller_entries = await asyncio.gather(
        _safe_fetch(_page_through(client, "/lists/buyer_role/entries/query"), "buyer_role"),
        _safe_fetch(_page_through(client, "/lists/seller_role/entries/query"), "seller_role"),
    )
    # Before `_reconcile_roles`, which PATCHes `is_active` back to Attio:
    # reconciling across scopes would let a newer test entry demote a
    # production one. Same rule as the webhook path's `sync_*_role`.
    if buyer_entries is not None:
        buyer_entries = [e for e in buyer_entries if upsert.in_scope(e)]
    if seller_entries is not None:
        seller_entries = [e for e in seller_entries if upsert.in_scope(e)]

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
        ok, write_failed = await _write_and_verify(
            BuyerRole, "buyer_roles", rows, len(rows), verify_count=False
        )
        summary["buyer_role"] = (ok, reconcile_failed + write_failed)
        await _reconcile_into(
            summary,
            "buyer_role",
            "buyer_roles",
            {r["legacy_entry_id"] for r in rows if r.get("legacy_entry_id")},
        )

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
        ok, write_failed = await _write_and_verify(
            SellerRole, "seller_roles", rows, len(rows), verify_count=False
        )
        summary["seller_role"] = (ok, reconcile_failed + write_failed)
        await _reconcile_into(
            summary,
            "seller_role",
            "seller_roles",
            {r["legacy_entry_id"] for r in rows if r.get("legacy_entry_id")},
        )

    live_note_ids: set[str] = set()
    summary["note"] = await _sync_notes_full(client, live_note_ids)
    # Safe now that `notes.attio_id` exists: rows the meetings pipeline
    # authored without reaching Attio have a NULL key and cannot match.
    await _reconcile_into(summary, "note", "notes", live_note_ids)

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
