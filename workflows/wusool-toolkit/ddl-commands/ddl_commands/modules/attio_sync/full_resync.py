"""Nightly safety-net: a full page-through resync of DEV Attio into
Postgres, reusing the exact same per-record upsert functions the real-time
webhook path uses (`upsert.py`). Complements, not replaces, the webhook —
catches anything a missed delivery, an out-of-order race, or a paused
webhook (see the migration-pause runbook handed over separately) left
inconsistent.

Run via `python -m ddl_commands.modules.attio_sync.full_resync`, invoked on
a schedule by `.github/workflows/nightly-attio-sync.yml` — the same
SSM-into-the-toolkit-container pattern `_deploy.yml` already uses for
`alembic upgrade head` (RDS is private; the toolkit EC2 instance is the only
thing with a network path to it).

`buyer_role`/`seller_role` entries are deduped down to one representative
entry per organization before syncing: `upsert.sync_buyer_role`/
`sync_seller_role` already re-fetch every sibling entry for that
organization to run the `is_active` reconciliation regardless of which
specific entry triggered it, so calling it once per raw duplicate entry
would redo that same reconciliation N times for nothing.

Deletions are still out of scope here, for the same reason `upsert.py`
doesn't handle them per-event: only `organizations` gets pruned
(`removed_at`), matching `sync-postgres.ps1`'s existing convention; no other
table's stale rows are cleaned up by this pass either.
"""

import asyncio
import logging

from ddl_commands.config import get_settings
from ddl_commands.modules.attio_sync import upsert
from ddl_commands.modules.attio_sync import values as v
from ddl_commands.modules.attio_sync.retry import post_with_retry
from ddl_commands.shared.attio.client import AttioClient
from ddl_commands.shared.database import import_all_models

_logger = logging.getLogger("ddl_commands.attio_sync.full_resync")


async def _page_through(client: AttioClient, path: str) -> list[dict]:
    items: list[dict] = []
    offset = 0
    while True:
        response = await post_with_retry(client, path, {"limit": 500, "offset": offset})
        page = response.get("data", [])
        items.extend(page)
        if len(page) < 500:
            return items
        offset += 500


async def _object_record_ids(client: AttioClient, object_slug: str) -> list[str]:
    records = await _page_through(client, f"/objects/{object_slug}/records/query")
    return [v.record_id(r) for r in records]


async def _list_entry_ids(client: AttioClient, list_slug: str) -> list[str]:
    entries = await _page_through(client, f"/lists/{list_slug}/entries/query")
    return [v.entry_id(e) for e in entries]


async def _one_entry_id_per_org(client: AttioClient, list_slug: str) -> list[str]:
    """One representative entry id per distinct parent organization —
    `sync_buyer_role`/`sync_seller_role` reconcile every duplicate for that
    org regardless of which one is passed in, so syncing once per org
    (not once per raw entry) gets the same result without redoing that
    reconciliation N times."""
    entries = await _page_through(client, f"/lists/{list_slug}/entries/query")
    representative_by_org: dict[str, str] = {}
    for entry in entries:
        representative_by_org.setdefault(v.parent_id(entry), v.entry_id(entry))
    return list(representative_by_org.values())


async def _sync_all(client: AttioClient, slug: str, ids: list[str], sync_fn) -> tuple[int, int]:
    ok = 0
    failed = 0
    for record_id in ids:
        try:
            await sync_fn(client, record_id)
            ok += 1
        except Exception:
            failed += 1
            _logger.error("full resync: failed to sync %s %s", slug, record_id, exc_info=True)
    return ok, failed


async def run() -> None:
    import_all_models()
    client = AttioClient(get_settings().attio_api_key)

    # Users first: organizations/people/deals reference users.attio_id via
    # owner_attio_id (guarded with CASE WHEN EXISTS in upsert.py) -- syncing
    # users before anything else means those references resolve on the
    # first pass instead of needing a second nightly run to catch up.
    users_synced = 0
    users_failed = 0
    try:
        users_synced = await upsert.sync_all_users(client)
    except Exception:
        users_failed = 1
        _logger.error("full resync: failed to sync users", exc_info=True)
    _logger.info("full resync: users — synced=%d", users_synced)

    plan = [
        ("organizations", _object_record_ids(client, "organizations"), upsert.sync_organization),
        ("person", _object_record_ids(client, "person"), upsert.sync_person),
        ("deals", _object_record_ids(client, "deals"), upsert.sync_deal),
        ("buyer_role", _one_entry_id_per_org(client, "buyer_role"), upsert.sync_buyer_role),
        ("seller_role", _one_entry_id_per_org(client, "seller_role"), upsert.sync_seller_role),
    ]

    summary: dict[str, tuple[int, int]] = {"users": (users_synced, users_failed)}
    for slug, ids_coro, sync_fn in plan:
        try:
            ids = await ids_coro
        except Exception:
            # A failure just listing this entity's records (Attio 500, rate
            # limit exhausted, malformed page) must not abort the whole run --
            # every entity after this one in `plan` still needs its chance to
            # sync tonight. Counted as a full failure for this entity alone.
            _logger.error("full resync: failed to list %s records", slug, exc_info=True)
            summary[slug] = (0, 1)
            continue
        _logger.info("full resync: %s — %d records", slug, len(ids))
        summary[slug] = await _sync_all(client, slug, ids, sync_fn)

    total_ok = sum(ok for ok, _ in summary.values())
    total_failed = sum(failed for _, failed in summary.values())
    for slug, (ok, failed) in summary.items():
        _logger.info("full resync: %-14s synced=%-5d failed=%d", slug, ok, failed)
    _logger.info("full resync complete: synced=%d failed=%d", total_ok, total_failed)

    if total_failed:
        # Non-zero exit code — the SSM/GH Actions caller must see this as failed.
        raise SystemExit(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    asyncio.run(run())


if __name__ == "__main__":
    main()
