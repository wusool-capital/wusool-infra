"""`SqlAlchemyDealStageRecorder` — writes `deal_stage_events` and the linked
`deal.stage_changed` activity.

Two writers move a deal's stage into Postgres: the Attio webhook sync and a
match approval (which writes Attio first, so the webhook echoes it back).
Both read the current stage under a row lock before their upsert and record
only a real change, so whichever commits second sees no change and records
nothing, instead of dropping or doubling the transition.

Not covered: two concurrent first-ever writes of one deal both see no row and
can each record a creation; the nightly batch resync writes no stage events.
"""

import logging
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, insert, text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import DealStageEvent
from app.modules.activities.domain.event import ActivityActor, ActivityEvent
from app.modules.activities.domain.payloads import StageChangePayload
from app.modules.activities.domain.vocabulary import ActivitySource, EventType, SubjectType
from app.modules.activities.persistence.recorder import SqlAlchemyActivityRecorder

_logger = logging.getLogger(__name__)

_CURRENT_STAGE = text("SELECT stage FROM deals WHERE attio_id = :attio_id FOR UPDATE")


class SqlAlchemyDealStageRecorder:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
        self._activities = SqlAlchemyActivityRecorder(session)

    async def current_stage(self, deal_attio_id: str) -> str | None:
        """The stored stage, row-locked until the caller's transaction ends.
        None for a deal with no row yet or no stage."""
        result = await self._session.execute(_CURRENT_STAGE, {"attio_id": deal_attio_id})
        return result.scalar_one_or_none()

    async def record_change(
        self,
        *,
        deal_attio_id: str,
        previous_stage: str | None,
        new_stage: str | None,
        actor: ActivityActor,
        source: ActivitySource,
        occurred_at: datetime | None = None,
    ) -> UUID | None:
        """Call after the `deals` upsert, so the FK target exists. Returns the
        event id, or None when the stage did not change."""
        if new_stage is None or new_stage == previous_stage:
            return None
        try:
            # Savepoint: missing history must never block syncing the stage itself.
            async with self._session.begin_nested():
                return await self._insert(
                    deal_attio_id, previous_stage, new_stage, actor, source, occurred_at
                )
        except SQLAlchemyError:
            _logger.exception("deal_stage_record_failed deal=%s", deal_attio_id)
            return None

    async def _insert(
        self,
        deal_attio_id: str,
        previous_stage: str | None,
        new_stage: str,
        actor: ActivityActor,
        source: ActivitySource,
        occurred_at: datetime | None,
    ) -> UUID:
        result = await self._session.execute(
            insert(DealStageEvent)
            .values(
                deal_attio_id=deal_attio_id,
                from_stage=previous_stage,
                to_stage=new_stage,
                source=source.value,
                ts=occurred_at if occurred_at is not None else func.now(),
            )
            .returning(DealStageEvent.id)
        )
        event_id = result.scalar_one()
        await self._activities.record(
            ActivityEvent(
                subject_type=SubjectType.DEAL,
                event_type=EventType.DEAL_STAGE_CHANGED,
                source=source,
                actor=actor,
                payload=StageChangePayload(from_stage=previous_stage, to_stage=new_stage),
                subject_attio_id=deal_attio_id,
                occurred_at=occurred_at,
                deal_stage_event_id=event_id,
            )
        )
        return event_id
