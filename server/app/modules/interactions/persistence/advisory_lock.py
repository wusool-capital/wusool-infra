"""A Postgres session lock, so only one process runs an ingest pass at a time.

Dev and prod can share a database and a Google tenant, and a deploy briefly runs two
containers. The lock is what stops them reading and writing the same mailboxes at once.
"""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncEngine


@asynccontextmanager
async def try_advisory_lock(engine: AsyncEngine, key: int) -> AsyncIterator[bool]:
    """Yields whether the lock was won. A won lock is held until the block ends.

    The lock belongs to one connection, so it is taken on a connection of its own and never
    returned to the pool while held. If the process dies, Postgres drops the lock with it.
    """
    async with engine.connect() as connection:
        # Autocommit keeps a transaction from staying open for as long as a backfill runs.
        await connection.execution_options(isolation_level="AUTOCOMMIT")
        won = bool((await connection.execute(select(func.pg_try_advisory_lock(key)))).scalar_one())
        try:
            yield won
        finally:
            if won:
                await connection.execute(select(func.pg_advisory_unlock(key)))
