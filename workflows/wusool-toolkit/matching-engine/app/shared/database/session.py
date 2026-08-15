"""Engine/sessionmaker construction.

`create_async_engine` is lazy — no connection is made until a session is
actually used. Keep it that way so the app can be imported, tested, and
booted without live database connectivity (e.g. no SSM tunnel in CI).
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import get_settings


@lru_cache
def get_engine() -> AsyncEngine:
    """Return a cached, process-wide async engine. Does not connect eagerly."""
    settings = get_settings()
    return create_async_engine(settings.database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    """Return a cached sessionmaker bound to the process-wide engine."""
    return async_sessionmaker(bind=get_engine(), expire_on_commit=False)
