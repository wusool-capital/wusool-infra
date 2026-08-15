"""Lightweight database health checking. Never touches business tables."""

from sqlalchemy import text

from ddl_commands.shared.database.session import get_engine


async def check_database_connectivity() -> bool:
    """Run `SELECT 1` against the database. Used by the readiness endpoint only."""
    engine = get_engine()
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
