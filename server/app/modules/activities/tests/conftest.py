"""Test fixtures.

`db_session` runs each integration test inside a transaction that is rolled
back at teardown, and skips when the database is unreachable. Point
`DATABASE_URL` at a disposable local Postgres, never at the dev or prod RDS.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.utilities.persistence.engine import get_engine
from app.modules.utilities.persistence.registry import import_all_models

import_all_models()


def _async_url(url: str) -> str:
    return url.replace("postgresql://", "postgresql+asyncpg://", 1)


@pytest.fixture
async def db_session():
    engine = get_engine(_async_url(os.environ["DATABASE_URL"]))
    try:
        conn = await engine.connect()
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
