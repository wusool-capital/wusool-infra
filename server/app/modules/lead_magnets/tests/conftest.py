"""Test fixtures.

Dummy env vars are set at import time, before any test module calls
`app.modules.lead_magnets.config.get_settings()`, so collection never needs
a real `.env` — matching `meetings/tests/conftest.py`.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ.setdefault("ATTIO_API_KEY", "test-attio-key")
os.environ.setdefault("ATTIO_IS_TEST", "true")

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.lead_magnets.api import dependencies as deps
from app.modules.lead_magnets.persistence.database import get_engine
from app.modules.utilities.persistence.registry import import_all_models

import_all_models()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """`_get_limiter()` caches one process-wide `FixedWindowRateLimiter` —
    without a reset, requests from earlier tests in the same session accrue
    against the same "testclient" IP key and can trip a later, unrelated
    test's request with a spurious 429 depending on run order.
    """
    deps._limiter = None
    yield
    deps._limiter = None


@pytest.fixture
async def db_session():
    """A session on a transaction rolled back at teardown, so the existing
    dataset is never mutated. Skips outright if the database is unreachable.
    Mirrors `meetings`' and `matching_engine`'s own fixture.
    """
    engine = get_engine()
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
