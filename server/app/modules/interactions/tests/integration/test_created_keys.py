"""The record of what the engine created: one Attio id per email or domain."""

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AutoCreateKey
from app.modules.interactions.application.ports.auto_create import CreatedKind
from app.modules.interactions.persistence.created_keys import SqlAlchemyCreatedKeys


async def test_a_key_is_saved_once_and_read_back(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    key = f"{record_prefix}sara@acme.com"
    keys = SqlAlchemyCreatedKeys(sessionmaker)
    try:
        assert await keys.get(CreatedKind.PERSON, key) is None

        await keys.save(CreatedKind.PERSON, key, "person-1")
        await keys.save(CreatedKind.PERSON, key, "person-2")

        assert await keys.get(CreatedKind.PERSON, key) == "person-1"
        assert await keys.get(CreatedKind.ORGANIZATION, key) is None
    finally:
        async with sessionmaker() as session, session.begin():
            await session.execute(delete(AutoCreateKey).where(AutoCreateKey.key == key))
