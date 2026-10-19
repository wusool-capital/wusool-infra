"""`attio_sync_state` — what the nightly full resync last did. State, not
history: one upserted row, no activity."""

from typing import Literal

from pydantic import BaseModel
from sqlalchemy import text

from app.modules.ddl_commands.persistence.database import get_sessionmaker

SYNC_NAME = "attio_full_resync"


class ObjectResult(BaseModel):
    name: str
    synced: int
    failed: int


class ResyncSummary(BaseModel):
    status: Literal["succeeded", "failed"]
    duration_seconds: float
    total_synced: int
    total_failed: int
    objects: list[ObjectResult]
    raw_events_pruned: int
    error: str | None = None


# `last_synced_at` moves only on a clean run; `metadata` holds the latest attempt.
_UPSERT = text(
    """
    INSERT INTO attio_sync_state(sync_name, last_synced_at, metadata, updated_at)
    VALUES (:sync_name, CASE WHEN :ok THEN now() END, CAST(:metadata AS jsonb), now())
    ON CONFLICT (sync_name) DO UPDATE SET
        last_synced_at = CASE WHEN :ok THEN now() ELSE attio_sync_state.last_synced_at END,
        metadata = excluded.metadata,
        updated_at = now()
    """
)


async def record_resync_state(summary: ResyncSummary) -> None:
    async with get_sessionmaker()() as session:
        await session.execute(
            _UPSERT,
            {
                "sync_name": SYNC_NAME,
                "ok": summary.status == "succeeded",
                "metadata": summary.model_dump_json(),
            },
        )
        await session.commit()
