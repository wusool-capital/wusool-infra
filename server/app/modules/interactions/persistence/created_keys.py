"""Implements `CreatedKeysPort` on `auto_create_keys`."""

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AutoCreateKey
from app.modules.interactions.application.ports.auto_create import CreatedKind


class SqlAlchemyCreatedKeys:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def get(self, kind: CreatedKind, key: str) -> str | None:
        stmt = select(AutoCreateKey.record_attio_id).where(
            AutoCreateKey.kind == kind.value, AutoCreateKey.key == key
        )
        async with self._sessionmaker() as session:
            return (await session.execute(stmt)).scalar_one_or_none()

    async def save(self, kind: CreatedKind, key: str, record_id: str) -> None:
        stmt = (
            insert(AutoCreateKey)
            .values(kind=kind.value, key=key, record_attio_id=record_id)
            .on_conflict_do_nothing(constraint="uq_auto_create_keys_kind_key")
        )
        async with self._sessionmaker() as session, session.begin():
            await session.execute(stmt)
