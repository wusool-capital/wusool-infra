"""Async SQLAlchemy engine/session wiring for the existing `wusool_crm` database.

This module only connects to the existing database. It does not define ORM
models, create tables, or run migrations — schema mapping is Phase 2.
"""

from .engine import get_engine, get_sessionmaker

__all__ = ["get_engine", "get_sessionmaker"]
