"""Integration fixtures: a real Postgres, skipped when none is reachable. Each test gets its own
mailbox and record ids, and removes what it created, so runs never see each other's rows."""

import uuid
from collections.abc import AsyncIterator

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, MailboxSyncCursor, Organization, Person
from app.modules.interactions.config import get_settings
from app.modules.utilities.persistence.engine import get_sessionmaker


@pytest.fixture
async def sessionmaker() -> async_sessionmaker[AsyncSession]:
    maker = get_sessionmaker(get_settings().database_url)
    try:
        async with maker() as session:
            await session.connection()
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")
    return maker


@pytest.fixture
async def mailbox(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[str]:
    address = f"it-{uuid.uuid4().hex[:8]}@wusoolcapital.com"
    yield address
    async with sessionmaker() as session, session.begin():
        await session.execute(delete(Interaction).where(Interaction.mailbox == address))
        await session.execute(delete(MailboxSyncCursor).where(MailboxSyncCursor.mailbox == address))


@pytest.fixture
async def record_prefix(sessionmaker: async_sessionmaker[AsyncSession]) -> AsyncIterator[str]:
    """A unique prefix for Person and Organization ids; everything under it is removed after."""
    prefix = f"it-{uuid.uuid4().hex[:8]}-"
    yield prefix
    async with sessionmaker() as session, session.begin():
        await session.execute(delete(Person).where(Person.attio_id.like(f"{prefix}%")))
        await session.execute(delete(Organization).where(Organization.attio_id.like(f"{prefix}%")))
