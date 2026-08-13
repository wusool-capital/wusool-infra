"""Schema-drift detection against the existing, externally-owned database.

This reflects the live database and compares it to what this application's
ORM models declare. It never modifies the database — if a required table or
column is missing, that's reported so a test can fail clearly; nothing here
creates, alters, or generates a migration for anything.

Test-time only (see `tests/integration/test_schema_drift.py`), not an
app-startup gate — running this at import/startup time would reintroduce a
hard database dependency that Phase 1 deliberately avoided so the app can
boot without a live DB (e.g. no SSM tunnel in local dev).
"""

from sqlalchemy import inspect
from sqlalchemy.ext.asyncio import AsyncEngine


def _reflect_sync(sync_conn) -> dict[str, set[str]]:
    inspector = inspect(sync_conn)
    return {
        table: {column["name"] for column in inspector.get_columns(table)}
        for table in inspector.get_table_names()
    }


async def find_schema_drift(engine: AsyncEngine, expected: dict[str, set[str]]) -> list[str]:
    """Compare `expected` {table: {columns}} against the live database.

    Returns a list of human-readable mismatches; empty means no drift.
    """
    async with engine.connect() as conn:
        actual = await conn.run_sync(_reflect_sync)

    mismatches: list[str] = []
    for table, columns in expected.items():
        if table not in actual:
            mismatches.append(f"missing table: {table}")
            continue
        for column in columns - actual[table]:
            mismatches.append(f"missing column: {table}.{column}")
    return mismatches
