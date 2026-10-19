"""`SqlAlchemyActivityRecorder` — the single writer of `activities` rows."""

import logging
from typing import Annotated

from pydantic import Field, TypeAdapter
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities.domain.event import ActivityEvent
from app.modules.activities.domain.payloads import ActivityPayload

_logger = logging.getLogger(__name__)

_PAYLOAD = TypeAdapter(Annotated[ActivityPayload, Field(discriminator="kind")])

# actor_attio_id is resolved through `users` so an unknown member becomes NULL
# instead of an FK failure. The ON CONFLICT target must match the partial
# unique index `uq_activities_idempotency_key`.
_INSERT = text(
    """
    INSERT INTO activities(
        subject_type, subject_attio_id, subject_uuid, event_type, source,
        actor_type, actor_ref, actor_attio_id, outcome, ts, payload, idempotency_key,
        tool_run_id, match_result_id, meeting_id, command_run_id,
        deal_stage_event_id, signal_id
    ) VALUES (
        :subject_type, :subject_attio_id, CAST(:subject_uuid AS uuid), :event_type, :source,
        :actor_type, :actor_ref,
        (SELECT attio_id FROM users WHERE attio_id = :actor_attio_id),
        :outcome, COALESCE(CAST(:ts AS timestamptz), now()), CAST(:payload AS jsonb),
        :idempotency_key,
        CAST(:tool_run_id AS uuid), CAST(:match_result_id AS uuid), CAST(:meeting_id AS uuid),
        CAST(:command_run_id AS uuid), CAST(:deal_stage_event_id AS uuid),
        CAST(:signal_id AS uuid)
    )
    ON CONFLICT (idempotency_key) WHERE idempotency_key IS NOT NULL DO NOTHING
    """
)


def _text_or_none(value: object) -> str | None:
    return None if value is None else str(value)


class SqlAlchemyActivityRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def record(self, event: ActivityEvent) -> None:
        try:
            # Savepoint: a failed insert must not poison the caller's transaction.
            async with self._session.begin_nested():
                await self._session.execute(_INSERT, self._params(event))
        except Exception:
            _logger.exception(
                "activity_record_failed event_type=%s subject_type=%s",
                event.event_type,
                event.subject_type,
            )

    @staticmethod
    def _params(event: ActivityEvent) -> dict[str, str | None]:
        return {
            "subject_type": event.subject_type.value,
            "subject_attio_id": event.subject_attio_id,
            "subject_uuid": _text_or_none(event.subject_uuid),
            "event_type": event.event_type.value,
            "source": event.source.value,
            "actor_type": event.actor.type.value,
            "actor_ref": event.actor.ref,
            "actor_attio_id": event.actor.attio_member_id,
            "outcome": event.outcome,
            "ts": None if event.occurred_at is None else event.occurred_at.isoformat(),
            "payload": _PAYLOAD.dump_json(event.payload).decode(),
            "idempotency_key": event.idempotency_key,
            "tool_run_id": _text_or_none(event.tool_run_id),
            "match_result_id": _text_or_none(event.match_result_id),
            "meeting_id": _text_or_none(event.meeting_id),
            "command_run_id": _text_or_none(event.command_run_id),
            "deal_stage_event_id": _text_or_none(event.deal_stage_event_id),
            "signal_id": _text_or_none(event.signal_id),
        }
