"""Async SQLAlchemy sessionmaker for the `wusool_crm` database, like every module's own."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.modules.interactions.config import get_settings
from app.modules.utilities.persistence import engine as _engine


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _engine.get_sessionmaker(get_settings().database_url)


@lru_cache
def get_engine() -> AsyncEngine:
    """The same process-wide engine the sessionmaker uses, for the advisory lock."""
    return _engine.get_engine(get_settings().database_url)
