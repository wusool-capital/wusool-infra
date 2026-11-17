"""Record what Attio holds today, before the engine writes (AZM-159 PR 4).

    python -m app.modules.interactions.scripts.seed_attio_sent_values

Reads Attio and writes only the engine's own `attio_sent_values` table. Nothing is sent to
Attio. Safe to run again: a field that already has a row is never overwritten. Run it inside
the deployed container, never from a laptop against the dev or prod database.
"""

import asyncio

from app.modules.interactions.bootstrap import run_attio_seed


async def main() -> None:
    for report in await run_attio_seed():
        note = "" if report.marked else "  NOT marked done: no records were read"
        print(
            f"{report.object.value}: read {report.records_read} records, "
            f"stored {report.rows_stored} new values{note}"
        )


if __name__ == "__main__":
    asyncio.run(main())
