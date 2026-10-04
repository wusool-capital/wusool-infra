"""Async SQLAlchemy engine/session wiring for the existing `wusool_crm`
database. Thin wrapper around `app.modules.utilities`, mirroring every other
module's own `persistence/database.py`.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.discovery.config import get_settings
from app.modules.utilities.persistence import engine as _engine


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _engine.get_sessionmaker(get_settings().database_url)
