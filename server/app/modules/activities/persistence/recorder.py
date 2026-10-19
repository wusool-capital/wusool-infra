"""`SqlAlchemyActivityRecorder` — the single writer of `activities` rows."""

import logging
from datetime import datetime
from typing import Annotated, TypedDict
from uuid import UUID

from pydantic import Field, TypeAdapter
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities.domain.event import ActivityEvent
from app.modules.activities.domain.payloads import ActivityPayload

_logger = logging.getLogger(__name__)

_PAYLOAD = TypeAdapter(Annotated[ActivityPayload, Field(discriminator="kind")])

# Unknown actors become NULL, not FK errors. ON CONFLICT must match `uq_activities_idempotency_key`.
_INSERT = text(
    """
    INSERT INTO activities(
        subject_type, subject_attio_id, subject_uuid, event_type, source,
        actor_type, actor_ref, actor_attio_id, outcome, ts, payload, idempotency_key,
        ledger_type, ledger_id
    ) VALUES (
        :subject_type, :subject_attio_id, CAST(:subject_uuid AS uuid), :event_type, :source,
        :actor_type, :actor_ref,
        (SELECT attio_id FROM users WHERE attio_id = :actor_attio_id),
        :outcome, COALESCE(CAST(:ts AS timestamptz), now()), CAST(:payload AS jsonb),
        :idempotency_key,
        :ledger_type, CAST(:ledger_id AS uuid)
    )
    ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
    """
)


class _InsertParams(TypedDict):
    subject_type: str
    subject_attio_id: str | None
    subject_uuid: str | None
    event_type: str
    source: str
    actor_type: str
    actor_ref: str | None
    actor_attio_id: str | None
    outcome: str | None
    ts: datetime | None
    payload: str
    idempotency_key: str | None
    ledger_type: str | None
    ledger_id: str | None


def _uuid_text(value: UUID | None) -> str | None:
    return None if value is None else str(value)


def _params(event: ActivityEvent) -> _InsertParams:
    return {
        "subject_type": event.subject_type.value,
        "subject_attio_id": event.subject_attio_id,
        "subject_uuid": _uuid_text(event.subject_uuid),
        "event_type": event.event_type.value,
        "source": event.source.value,
        "actor_type": event.actor.type.value,
        "actor_ref": event.actor.ref,
        "actor_attio_id": event.actor.attio_member_id,
        "outcome": event.outcome,
        "ts": event.occurred_at,
        "payload": _PAYLOAD.dump_json(event.payload, warnings="error").decode(),
        "idempotency_key": event.idempotency_key,
        "ledger_type": event.ledger.type.value if event.ledger else None,
        "ledger_id": _uuid_text(event.ledger.id if event.ledger else None),
    }


class SqlAlchemyActivityRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: ActivityEvent) -> None:
        # Built outside the try: a serialization bug is a programming error and
        # must fail loudly in tests, not vanish as a missing history row.
        params = _params(event)
        try:
            # Savepoint: a failed insert must not poison the caller's transaction.
            async with self._session.begin_nested():
                await self._session.execute(_INSERT, params)
        except SQLAlchemyError:
            _logger.exception(
                "activity_record_failed event_type=%s subject_type=%s",
                event.event_type,
                event.subject_type,
            )
