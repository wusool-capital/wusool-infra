"""Lightweight database health checking. Never touches business tables."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine


async def check_database_connectivity(engine: AsyncEngine) -> bool:
    """Run `SELECT 1` against the database. Used by the readiness endpoint only."""
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return True
