"""`activities` rejects every UPDATE, DELETE and TRUNCATE; INSERT stays open."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    EventType,
    SqlAlchemyActivityRecorder,
    SubjectType,
)


async def _record(session: AsyncSession) -> str:
    subject = f"org-{uuid.uuid4()}"
    await SqlAlchemyActivityRecorder(session).record(
        ActivityEvent(
            subject_type=SubjectType.ORGANIZATION,
            event_type=EventType.SELLER_EDITED,
            source=ActivitySource.SLACK,
            actor=ActivityActor.slack("U1"),
            subject_attio_id=subject,
        )
    )
    return subject


async def test_insert_still_works(db_session: AsyncSession) -> None:
    subject = await _record(db_session)

    count = (
        await db_session.execute(
            text("SELECT count(*) FROM activities WHERE subject_attio_id = :s"), {"s": subject}
        )
    ).scalar_one()
    assert count == 1


async def test_update_is_rejected(db_session: AsyncSession) -> None:
    subject = await _record(db_session)

    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(
            text("UPDATE activities SET outcome = 'tampered' WHERE subject_attio_id = :s"),
            {"s": subject},
        )


async def test_delete_is_rejected(db_session: AsyncSession) -> None:
    subject = await _record(db_session)

    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(
            text("DELETE FROM activities WHERE subject_attio_id = :s"), {"s": subject}
        )


async def test_truncate_is_rejected(db_session: AsyncSession) -> None:
    with pytest.raises(DBAPIError, match="append-only"):
        await db_session.execute(text("TRUNCATE activities"))


async def test_the_ledger_pair_must_be_set_together(db_session: AsyncSession) -> None:
    with pytest.raises(DBAPIError, match="activities_ledger_pair"):
        await db_session.execute(
            text(
                "INSERT INTO activities(subject_type, subject_attio_id, event_type, actor_type, "
                "ledger_type) VALUES ('Person', 'p', 'seller.added', 'system', 'tool_run')"
            )
        )


async def test_the_ledger_type_is_a_closed_list(db_session: AsyncSession) -> None:
    with pytest.raises(DBAPIError, match="activities_ledger_type_check"):
        await db_session.execute(
            text(
                "INSERT INTO activities(subject_type, subject_attio_id, event_type, actor_type, "
                "ledger_type, ledger_id) "
                "VALUES ('Person', 'p', 'seller.added', 'system', 'nonsense', gen_random_uuid())"
            )
        )
