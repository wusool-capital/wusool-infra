"""Engine and sessionmaker bound to this module's own `DATABASE_URL`.

Thin by design — the pooling and construction live in
`utilities.persistence.engine`, shared with every other module. No
`Base`/`import_all_models` re-export: `server/main.py` already registers the
ORM models once, and this module owns no table of its own (`tool_runs`
arrived with migration `f7a2c9e14b83`).
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.modules.lead_magnets.config import get_settings
from app.modules.utilities.persistence import engine as _engine


@lru_cache
def get_engine() -> AsyncEngine:
    return _engine.get_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _engine.get_sessionmaker(get_settings().database_url)
