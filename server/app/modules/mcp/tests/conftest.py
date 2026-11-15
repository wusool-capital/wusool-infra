"""Dummy env vars so collection never needs a real `.env`; the integration test
uses `DATABASE_URL`, which `checks.sh` points at a disposable Postgres."""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ["AWS_SECRETS_MANAGER_SECRET_ID"] = ""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.mcp.config import get_database_settings
from app.modules.utilities.persistence import engine as _engine
from app.modules.utilities.persistence.registry import import_all_models

import_all_models()


@pytest.fixture
async def db_session():
    """A session on a transaction rolled back at teardown. Skips if the database is
    unreachable."""
    db_engine = _engine.get_engine(get_database_settings().database_url)
    try:
        conn = await db_engine.connect()
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    trans = await conn.begin()
    session = AsyncSession(bind=conn, join_transaction_mode="create_savepoint")
    try:
        yield session
    finally:
        await session.close()
        await trans.rollback()
        await conn.close()
