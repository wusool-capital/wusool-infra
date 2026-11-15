"""Engine and sessionmaker bound to `DATABASE_URL`, used only to record tool calls."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.mcp.config import get_database_settings
from app.modules.utilities.persistence import engine as _engine


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _engine.get_sessionmaker(get_database_settings().database_url)
