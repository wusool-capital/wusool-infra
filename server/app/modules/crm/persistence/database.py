"""Engine and sessionmaker bound to this module's own `DATABASE_URL`."""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.crm.config import get_settings
from app.modules.utilities.persistence import engine as _engine


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _engine.get_sessionmaker(get_settings().database_url)
