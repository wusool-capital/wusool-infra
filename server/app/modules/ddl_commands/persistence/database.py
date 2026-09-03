"""Async SQLAlchemy engine/session wiring for the existing `wusool_crm` database.

This module only connects to the existing database. It does not define ORM
models, create tables, or run migrations — models under `app/models/` map
the existing schema as-is; nothing here generates DDL.

Thin wrapper around `app.modules.utilities`, binding this module's own
`get_settings().database_url` so every existing no-arg caller
(`get_engine()`, `get_sessionmaker()`, `check_database_connectivity()`)
keeps working unchanged.
"""

from functools import lru_cache

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.models.base import Base
from app.modules.ddl_commands.config import get_settings
from app.modules.utilities.persistence import engine as _engine
from app.modules.utilities.persistence import health as _health
from app.modules.utilities.persistence.registry import import_all_models

__all__ = [
    "Base",
    "check_database_connectivity",
    "get_engine",
    "get_sessionmaker",
    "import_all_models",
]


@lru_cache
def get_engine() -> AsyncEngine:
    return _engine.get_engine(get_settings().database_url)


@lru_cache
def get_sessionmaker() -> async_sessionmaker[AsyncSession]:
    return _engine.get_sessionmaker(get_settings().database_url)


async def check_database_connectivity() -> bool:
    return await _health.check_database_connectivity(get_engine())
