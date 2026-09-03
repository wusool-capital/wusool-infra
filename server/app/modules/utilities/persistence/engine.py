"""Engine/sessionmaker construction.

`create_async_engine` is lazy — no connection is made until a session is
actually used. Keep it that way so the app can be imported, tested, and
booted without live database connectivity (e.g. no SSM tunnel in CI).

Parameterized by `database_url` rather than importing a specific module's
`config.get_settings()` — each module passes its own settings in from its
own `shared/database/__init__.py` barrel. `lru_cache` keys on the argument,
so two modules pointed at the same URL share one engine/pool rather than
opening a redundant second connection pool to the same database.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)


@lru_cache
def get_engine(database_url: str) -> AsyncEngine:
    """Return a cached, process-wide async engine. Does not connect eagerly."""
    return create_async_engine(database_url, pool_pre_ping=True)


@lru_cache
def get_sessionmaker(database_url: str) -> async_sessionmaker[AsyncSession]:
    """Return a cached sessionmaker bound to the process-wide engine."""
    return async_sessionmaker(bind=get_engine(database_url), expire_on_commit=False)
