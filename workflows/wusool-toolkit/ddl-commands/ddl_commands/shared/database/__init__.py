"""Async SQLAlchemy engine/session wiring for the existing `wusool_crm` database.

This module only connects to the existing database. It does not define ORM
models, create tables, or run migrations — models under `models/` map the
existing schema as-is; nothing here generates DDL.
"""

from ddl_commands.shared.database.health import check_database_connectivity
from ddl_commands.shared.database.registry import import_all_models
from ddl_commands.shared.database.session import get_engine, get_sessionmaker
from wusool_db.base import Base

__all__ = [
    "Base",
    "check_database_connectivity",
    "get_engine",
    "get_sessionmaker",
    "import_all_models",
]
