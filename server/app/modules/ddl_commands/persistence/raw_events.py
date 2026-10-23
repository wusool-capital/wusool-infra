"""`attio_raw_events` — one row per Attio webhook event, for replay and
debugging. Not part of the business timeline (`activities`).

No idempotency key: Attio events carry only ids, so two real updates to one
record look identical and a hash key would drop the second. The table is
append-only and pruned nightly (`prune_raw_events`).
"""

import logging
from uuid import UUID

from sqlalchemy import text

from app.modules.ddl_commands.persistence.database import get_sessionmaker

_logger = logging.getLogger("app.modules.ddl_commands.attio_sync")

_INSERT = text(
    "INSERT INTO attio_raw_events(event_type, payload) "
    "VALUES (:event_type, CAST(:payload AS jsonb)) RETURNING id"
)
_MARK_PROCESSED = text("UPDATE attio_raw_events SET processed_at = now() WHERE id = :id")
_PRUNE = text(
    """
    WITH deleted AS (
        DELETE FROM attio_raw_events
        WHERE received_at < now() - make_interval(days => :days)
        RETURNING 1
    )
    SELECT count(*) FROM deleted
    """
)


class RawEventLog:
    async def record(self, *, event_type: str, payload_json: str) -> UUID | None:
        try:
            async with get_sessionmaker()() as session:
                result = await session.execute(
                    _INSERT, {"event_type": event_type, "payload": payload_json}
                )
                raw_event_id = result.scalar_one()
                await session.commit()
                return raw_event_id
        except Exception:
            _logger.exception("attio_raw_event_record_failed event_type=%s", event_type)
            return None

    async def mark_processed(self, raw_event_id: UUID) -> None:
        try:
            async with get_sessionmaker()() as session:
                await session.execute(_MARK_PROCESSED, {"id": raw_event_id})
                await session.commit()
        except Exception:
            _logger.exception("attio_raw_event_mark_failed id=%s", raw_event_id)


async def prune_raw_events(retention_days: int) -> int:
    """Deletes events older than `retention_days`; returns how many."""
    async with get_sessionmaker()() as session:
        result = await session.execute(_PRUNE, {"days": retention_days})
        await session.commit()
        return result.scalar_one()
