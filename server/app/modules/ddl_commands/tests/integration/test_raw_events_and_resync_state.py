"""`attio_raw_events` log and `attio_sync_state` against a rolled-back transaction."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ddl_commands.persistence import raw_events, resync_state
from app.modules.ddl_commands.persistence.raw_events import RawEventLog, prune_raw_events
from app.modules.ddl_commands.persistence.resync_state import (
    ObjectResult,
    ResyncSummary,
    record_resync_state,
)


@pytest.fixture(autouse=True)
def _use_rolled_back_sessions(monkeypatch, db_sessionmaker: async_sessionmaker[AsyncSession]):
    monkeypatch.setattr(raw_events, "get_sessionmaker", lambda: db_sessionmaker)
    monkeypatch.setattr(resync_state, "get_sessionmaker", lambda: db_sessionmaker)


async def _raw_row(db_sessionmaker: async_sessionmaker[AsyncSession], raw_id: uuid.UUID):
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text(
                    "SELECT event_type, payload, processed_at FROM attio_raw_events WHERE id = :id"
                ),
                {"id": raw_id},
            )
        ).one()


async def test_an_event_is_recorded_unprocessed_then_marked(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    log = RawEventLog()

    raw_id = await log.record(
        event_type="record.updated", payload_json='{"id": {"record_id": "r1"}}'
    )
    assert raw_id is not None
    row = await _raw_row(db_sessionmaker, raw_id)
    assert row.payload == {"id": {"record_id": "r1"}}
    assert row.processed_at is None

    await log.mark_processed(raw_id)
    assert (await _raw_row(db_sessionmaker, raw_id)).processed_at is not None


async def test_identical_events_are_both_kept(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    """Two real updates to one record carry identical ids, so there is no key to dedupe on."""
    log = RawEventLog()
    event_type = f"test.same.{uuid.uuid4()}"

    first = await log.record(event_type=event_type, payload_json="{}")
    second = await log.record(event_type=event_type, payload_json="{}")

    assert first is not None and second is not None and first != second


async def test_a_failed_write_returns_none_instead_of_raising() -> None:
    assert await RawEventLog().record(event_type="record.updated", payload_json="not json") is None


async def test_prune_removes_only_events_past_retention(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    old, fresh = f"test.old.{uuid.uuid4()}", f"test.fresh.{uuid.uuid4()}"
    async with db_sessionmaker() as session:
        await session.execute(
            text(
                "INSERT INTO attio_raw_events(event_type, payload, received_at) VALUES "
                "(:old, '{}', now() - interval '91 days'), "
                "(:fresh, '{}', now() - interval '89 days')"
            ),
            {"old": old, "fresh": fresh},
        )
        await session.commit()

    pruned = await prune_raw_events(90)

    assert pruned >= 1
    async with db_sessionmaker() as session:
        left = set(
            (
                await session.execute(
                    text("SELECT event_type FROM attio_raw_events WHERE event_type = ANY(:t)"),
                    {"t": [old, fresh]},
                )
            ).scalars()
        )
    assert left == {fresh}


def _summary(status: str, failed: int = 0) -> ResyncSummary:
    return ResyncSummary(
        status=status,  # type: ignore[arg-type]
        duration_seconds=12.5,
        total_synced=10,
        total_failed=failed,
        objects=[ObjectResult(name="organizations", synced=10, failed=failed)],
        raw_events_pruned=3,
    )


async def _state(db_sessionmaker: async_sessionmaker[AsyncSession]):
    async with db_sessionmaker() as session:
        return (
            await session.execute(
                text(
                    "SELECT last_synced_at, metadata FROM attio_sync_state "
                    "WHERE sync_name = 'attio_full_resync'"
                )
            )
        ).one()


async def test_a_failed_run_updates_the_metadata_but_not_last_synced_at(
    db_sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    await record_resync_state(_summary("succeeded"))
    succeeded = await _state(db_sessionmaker)
    assert succeeded.last_synced_at is not None
    assert succeeded.metadata["objects"] == [{"name": "organizations", "synced": 10, "failed": 0}]

    await record_resync_state(_summary("failed", failed=2))
    failed = await _state(db_sessionmaker)

    assert failed.last_synced_at == succeeded.last_synced_at
    assert failed.metadata["status"] == "failed"
    assert failed.metadata["total_failed"] == 2
