"""Test fixtures.

No real database connection or Slack credentials are required to run this
suite by default. Dummy env vars are set at import time (before any test
module imports `ddl_commands.main`, which reads settings at module load) so
collection never needs a real .env. The async engine is constructed but
never connected unless a test explicitly hits `/readiness` or uses the
`db_session` fixture below.

`DATABASE_URL` points at the real dev SSM-tunnel address on purpose: when a
tunnel is open, `tests/integration/` runs for real against `wusool_crm`; when
it isn't, `db_session` skips those tests cleanly rather than failing.
"""

import os

os.environ.setdefault("DATABASE_URL", "postgresql://user:pass@localhost:15432/wusool_crm")
os.environ.setdefault("SLACK_BOT_TOKEN", "xoxb-test-token")
os.environ.setdefault("SLACK_SIGNING_SECRET", "test-signing-secret")
os.environ.setdefault("ATTIO_API_KEY", "test-attio-key")

import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from wusool_db.models import Organization

from ddl_commands.shared.database import get_engine, import_all_models

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
    """Like `db_session`, but yields a sessionmaker rather than a single
    session — for code (the use cases) that opens several short-lived
    sessions itself. Each session it creates joins the same outer
    transaction via a savepoint, so everything still rolls back together at
    teardown.
    """
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
    """A throwaway `Organization`, inserted into `db_session`'s rolled-back
    transaction — never persisted beyond the test. Used as the parent row
    for throwaway buyer/seller roles, since both have a NOT NULL FK to it.
    """
    org = Organization(
        attio_id=f"test-org-{uuid.uuid4()}",
        name="Test Org",
        hq_country="AE",
        sector_focus=["Healthcare"],
    )
    db_session.add(org)
    await db_session.flush()
    return org
