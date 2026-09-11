"""Test fixtures. No real database connection or AWS/Firecrawl credentials
are required to run this suite by default — dummy env vars are set at
import time, mirroring every other module's own `tests/conftest.py`.
`DATABASE_URL` points at the real dev SSM-tunnel address on purpose: when a
tunnel is open, `tests/integration/` runs for real against `wusool_crm`;
when it isn't, `db_session` skips those tests cleanly rather than failing.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization
from app.modules.enrichment.persistence.database import get_engine, import_all_models

import_all_models()


@pytest.fixture
async def db_session():
    """Yields a session bound to a transaction that's rolled back at
    teardown, so the existing dataset is never mutated. Skips the test
    outright if the database isn't reachable (e.g. no SSM tunnel open).
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


@pytest.fixture
async def db_sessionmaker():
    """Like `db_session`, but yields a sessionmaker — for
    `SqlAlchemyRoleReader`, which opens its own short-lived session."""
    engine = get_engine()
    try:
        conn = await engine.connect()
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    trans = await conn.begin()
    maker = async_sessionmaker(
        bind=conn, join_transaction_mode="create_savepoint", expire_on_commit=False
    )
    try:
        yield maker
    finally:
        await trans.rollback()
        await conn.close()


@pytest.fixture
async def throwaway_org(db_session: AsyncSession) -> Organization:
    org = Organization(attio_id=f"test-org-{uuid.uuid4()}", name="Test Org", hq_country="AE")
    db_session.add(org)
    await db_session.flush()
    return org
