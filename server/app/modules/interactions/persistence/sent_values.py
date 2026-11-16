"""Implements `SentValuesPort` on the `attio_sent_values` table."""

from collections import defaultdict
from collections.abc import Mapping, Sequence
from typing import TypedDict

from sqlalchemy import func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import AttioSentValue
from app.modules.interactions.application.ports.sent_values import RecordValues, SeedRow
from app.modules.interactions.domain.attio_fields import AttioObject

# The reserved row that marks a seed as complete; real records never have an empty id.
_MARKER_RECORD = ""
_MARKER_FIELD = "__seeded__"
_BATCH = 2000
_UNIQUE = "uq_attio_sent_values_record_field"


class _SentRow(TypedDict):
    object: str
    record_attio_id: str
    field: str
    value: str | None


class _SeedDbRow(_SentRow):
    baseline: str | None


class SqlAlchemySentValues:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def load(self, obj: AttioObject) -> Mapping[str, RecordValues]:
        stmt = select(
            AttioSentValue.record_attio_id,
            AttioSentValue.field,
            AttioSentValue.value,
            AttioSentValue.baseline,
        ).where(
            AttioSentValue.object == obj.value,
            AttioSentValue.record_attio_id != _MARKER_RECORD,
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(stmt)).all()
        sent: dict[str, dict[str, str | None]] = defaultdict(dict)
        baseline: dict[str, dict[str, str | None]] = defaultdict(dict)
        for record_id, field, value, base in rows:
            sent[record_id][field] = value
            baseline[record_id][field] = base
        return {r: RecordValues(sent[r], baseline[r]) for r in sent}

    async def save(self, obj: AttioObject, record_id: str, fields: Mapping[str, str]) -> None:
        rows: list[_SentRow] = [
            {"object": obj.value, "record_attio_id": record_id, "field": field, "value": value}
            for field, value in fields.items()
        ]
        if not rows:
            return
        stmt = insert(AttioSentValue)
        stmt = stmt.on_conflict_do_update(
            constraint=_UNIQUE,
            # The baseline is the live Company value at seed time and is never rewritten.
            set_={"value": stmt.excluded.value, "updated_at": func.now()},
        )
        async with self._sessionmaker() as session, session.begin():
            await session.execute(stmt, rows)

    async def seed(self, obj: AttioObject, rows: Sequence[SeedRow]) -> int:
        stored: list[_SeedDbRow] = [
            {
                "object": obj.value,
                "record_attio_id": r.record_id,
                "field": r.field,
                "value": r.value,
                "baseline": r.baseline,
            }
            for r in rows
        ]
        written = 0
        for start in range(0, len(stored), _BATCH):
            stmt = (
                insert(AttioSentValue)
                .on_conflict_do_nothing()
                .returning(AttioSentValue.record_attio_id)
            )
            async with self._sessionmaker() as session, session.begin():
                written += len((await session.execute(stmt, stored[start : start + _BATCH])).all())
        return written

    async def is_seeded(self, obj: AttioObject) -> bool:
        stmt = select(AttioSentValue.field).where(
            AttioSentValue.object == obj.value,
            AttioSentValue.record_attio_id == _MARKER_RECORD,
            AttioSentValue.field == _MARKER_FIELD,
        )
        async with self._sessionmaker() as session:
            return (await session.execute(stmt)).first() is not None

    async def mark_seeded(self, obj: AttioObject) -> None:
        stmt = (
            insert(AttioSentValue)
            .values(
                object=obj.value,
                record_attio_id=_MARKER_RECORD,
                field=_MARKER_FIELD,
                value=None,
                baseline=None,
            )
            .on_conflict_do_nothing()
        )
        async with self._sessionmaker() as session, session.begin():
            await session.execute(stmt)
