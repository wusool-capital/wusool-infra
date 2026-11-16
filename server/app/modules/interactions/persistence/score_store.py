"""Implements `ScoreStorePort` on `organizations` and `person`.

`connection_strength_score` is Postgres-only: no Attio attribute exists for it, so the webhook
and the nightly resync never touch it and the engine writes it directly.
"""

from collections.abc import Mapping
from decimal import Decimal
from typing import cast

from sqlalchemy import Table, bindparam, select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization, Person
from app.modules.interactions.domain.attio_fields import AttioObject

_BATCH = 2000


def _table(obj: AttioObject) -> Table:
    model = Organization if obj is AttioObject.ORGANIZATIONS else Person
    # `__table__` is typed FromClause, and a mapped class always has a Table.
    return cast(Table, model.__table__)


class SqlAlchemyScoreStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def load(self, obj: AttioObject) -> Mapping[str, Decimal | None]:
        table = _table(obj)
        stmt = select(table.c.attio_id, table.c.connection_strength_score)
        async with self._sessionmaker() as session:
            return {record_id: score for record_id, score in (await session.execute(stmt)).all()}

    async def save(self, obj: AttioObject, scores: Mapping[str, Decimal]) -> None:
        table = _table(obj)
        stmt = (
            update(table)
            .where(table.c.attio_id == bindparam("b_id"))
            .values(connection_strength_score=bindparam("b_score"))
        )
        rows = [{"b_id": record_id, "b_score": score} for record_id, score in scores.items()]
        for start in range(0, len(rows), _BATCH):
            async with self._sessionmaker() as session, session.begin():
                await session.execute(stmt, rows[start : start + _BATCH])
