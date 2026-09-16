"""One-off backfill for `notes.attio_id` (migration f2b8d1c47e93).

Sets `attio_id = id` only for notes whose id Attio actually returns. Anything
else is left NULL, which is what keeps it out of deletion reconciliation.

Why this is not a SQL one-liner. `UPDATE notes SET attio_id = id` looks
equivalent and is not: `notes.id` holds Attio's record id when the meetings
pipeline's push succeeded, and a local `gen_random_uuid()` when it failed
(`meetings/application/publish.py` sets `note_attio_id = None`, and
`notes_repository.create` then lets the column default apply). Both are UUIDs.
Marking a locally-authored note as Attio-derived would hand it straight to the
reconciliation this column exists to protect it from, and the row would be
stamped `removed_at` on the next nightly -- silently hiding a meeting summary
that exists nowhere else. So membership is decided by Attio, never inferred.

Idempotent and re-runnable: only rows with `attio_id IS NULL` are considered,
and a row is only written if Attio knows its id.

Dry run by default. Requires DATABASE_URL (see rds-tunnel-runbook.md) and
SOURCE_ATTIO_API_KEY.

    python backfill-notes-attio-id.py            # report only
    python backfill-notes-attio-id.py --apply
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import urllib.request

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

ATTIO_API = "https://api.attio.com/v2"
PAGE = 500


def _fetch_attio_note_ids(api_key: str) -> set[str]:
    ids: set[str] = set()
    offset = 0
    while True:
        request = urllib.request.Request(
            f"{ATTIO_API}/objects/note/records/query",
            data=json.dumps({"limit": PAGE, "offset": offset}).encode(),
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
        with urllib.request.urlopen(request, timeout=90) as response:
            page = json.load(response)["data"]
        ids.update(record["id"]["record_id"] for record in page)
        if len(page) < PAGE:
            return ids
        offset += PAGE


async def main(apply: bool) -> int:
    database_url = os.environ.get("DATABASE_URL")
    api_key = os.environ.get("SOURCE_ATTIO_API_KEY")
    if not database_url or not api_key:
        print("DATABASE_URL and SOURCE_ATTIO_API_KEY are both required", file=sys.stderr)
        return 64

    attio_ids = _fetch_attio_note_ids(api_key)
    if not attio_ids:
        # The same refusal the nightly makes: an empty listing must never be
        # read as "Attio has no notes".
        print("Attio returned zero notes -- refusing to backfill.", file=sys.stderr)
        return 1
    print(f"Attio notes: {len(attio_ids)}")

    engine = create_async_engine(database_url.replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        async with engine.connect() as connection:
            rows = (
                await connection.execute(
                    text("SELECT id::text, note_type FROM notes WHERE attio_id IS NULL")
                )
            ).all()

        matched = [r[0] for r in rows if r[0] in attio_ids]
        unmatched = [r for r in rows if r[0] not in attio_ids]
        print(f"notes with attio_id unset: {len(rows)}")
        print(f"  found in Attio  -> will be set: {len(matched)}")
        print(f"  not in Attio    -> left NULL:   {len(unmatched)}")
        if unmatched:
            by_type: dict[str, int] = {}
            for _, note_type in unmatched:
                by_type[note_type] = by_type.get(note_type, 0) + 1
            print(f"    left-NULL breakdown by note_type: {by_type}")
            print("    (these are locally authored; reconciliation will skip them)")

        if not apply:
            print("\nDry run. Re-run with --apply to write.")
            return 0
        if not matched:
            print("\nNothing to write.")
            return 0

        async with engine.begin() as connection:
            await connection.execute(
                text("UPDATE notes SET attio_id = id::text WHERE id::text = ANY(:ids)"),
                {"ids": matched},
            )
        async with engine.connect() as connection:
            filled = (
                await connection.execute(
                    text("SELECT count(*) FROM notes WHERE attio_id IS NOT NULL")
                )
            ).scalar_one()
            still_null = (
                await connection.execute(text("SELECT count(*) FROM notes WHERE attio_id IS NULL"))
            ).scalar_one()
        print(f"\nDone. attio_id set on {filled} note(s); {still_null} left NULL.")
        return 0
    finally:
        await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="write (default is a dry run)")
    raise SystemExit(asyncio.run(main(parser.parse_args().apply)))
