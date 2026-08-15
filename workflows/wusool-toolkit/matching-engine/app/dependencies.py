"""FastAPI dependency wiring, shared across route modules."""

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.database import get_sessionmaker


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    sessionmaker = get_sessionmaker()
    async with sessionmaker() as session:
        yield session
