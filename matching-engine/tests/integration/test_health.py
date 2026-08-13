"""Health check against a real connection (separate from the no-DB boot test)."""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


async def test_select_1(db_session: AsyncSession) -> None:
    result = await db_session.execute(text("SELECT 1"))
    assert result.scalar_one() == 1
