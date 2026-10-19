import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import UTC, datetime

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

import app.modules.activities.persistence.recorder as recorder_module
from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    ActorType,
    EventType,
    LedgerRef,
    LedgerType,
    MatchDecisionPayload,
    SqlAlchemyActivityRecorder,
    SubjectType,
)


def _event(**overrides: object) -> ActivityEvent:
    base: Mapping[str, object] = {
        "subject_type": SubjectType.ORGANIZATION,
        "event_type": EventType.SELLER_EDITED,
        "source": ActivitySource.SLACK,
        "actor": ActivityActor.slack("U123"),
        "subject_attio_id": f"org-{uuid.uuid4()}",
    }
    return ActivityEvent(**{**base, **overrides})  # type: ignore[arg-type]


async def _count(session: AsyncSession, where: str, **params: str) -> int:
    result = await session.execute(text(f"SELECT count(*) FROM activities WHERE {where}"), params)
    return result.scalar_one()


async def _seed_org(session: AsyncSession, attio_id: str) -> None:
    await session.execute(
        text("INSERT INTO organizations(attio_id, name) VALUES (:id, 'Acme')"), {"id": attio_id}
    )


async def test_records_a_typed_row(db_session: AsyncSession) -> None:
    event = _event(payload=MatchDecisionPayload(deal_attio_id="d-1"), outcome="approved")
    await SqlAlchemyActivityRecorder(db_session).record(event)

    row = (
        await db_session.execute(
            text(
                "SELECT event_type, actor_type, actor_ref, source, outcome, payload "
                "FROM activities WHERE subject_attio_id = :id"
            ),
            {"id": event.subject_attio_id},
        )
    ).one()
    assert row.event_type == "seller.edited"
    assert row.actor_type == "slack_user"
    assert row.actor_ref == "U123"
    assert row.source == "slack"
    assert row.outcome == "approved"
    assert row.payload == {"kind": "match_decision", "deal_attio_id": "d-1"}


async def test_duplicate_idempotency_key_is_dropped(db_session: AsyncSession) -> None:
    key = f"test:{uuid.uuid4()}"
    recorder = SqlAlchemyActivityRecorder(db_session)
    await recorder.record(_event(idempotency_key=key))
    await recorder.record(_event(idempotency_key=key))
    assert await _count(db_session, "idempotency_key = :k", k=key) == 1


async def test_unknown_attio_member_becomes_null_not_an_fk_error(db_session: AsyncSession) -> None:
    event = _event(actor=ActivityActor(ActorType.ATTIO_MEMBER, "ghost", "ghost"))
    await SqlAlchemyActivityRecorder(db_session).record(event)
    row = (
        await db_session.execute(
            text("SELECT actor_attio_id, actor_ref FROM activities WHERE subject_attio_id = :id"),
            {"id": event.subject_attio_id},
        )
    ).one()
    assert row.actor_attio_id is None
    assert row.actor_ref == "ghost"


async def test_known_attio_member_is_linked(db_session: AsyncSession) -> None:
    member = f"member-{uuid.uuid4()}"
    await db_session.execute(
        text("INSERT INTO users(attio_id, name) VALUES (:id, 'Ada')"), {"id": member}
    )
    event = _event(actor=ActivityActor.attio("workspace-member", member))
    await SqlAlchemyActivityRecorder(db_session).record(event)
    row = (
        await db_session.execute(
            text("SELECT actor_attio_id FROM activities WHERE subject_attio_id = :id"),
            {"id": event.subject_attio_id},
        )
    ).one()
    assert row.actor_attio_id == member


async def test_a_database_error_is_swallowed_and_keeps_the_transaction(
    db_session: AsyncSession, monkeypatch: pytest.MonkeyPatch
) -> None:
    org_id = f"org-{uuid.uuid4()}"
    await _seed_org(db_session, org_id)
    recorder = SqlAlchemyActivityRecorder(db_session)

    # An INSERT into a column that does not exist is a database error.
    monkeypatch.setattr(recorder_module, "_INSERT", text("INSERT INTO activities(nope) VALUES (1)"))
    await recorder.record(_event())
    monkeypatch.undo()

    # The caller's transaction is still usable and its earlier work survives.
    await recorder.record(_event(subject_attio_id=org_id))
    org_count = (
        await db_session.execute(
            text("SELECT count(*) FROM organizations WHERE attio_id = :id"), {"id": org_id}
        )
    ).scalar_one()
    assert org_count == 1
    assert await _count(db_session, "subject_attio_id = :id", id=org_id) == 1


async def test_a_ledger_reference_is_stored_as_a_type_and_id(db_session: AsyncSession) -> None:
    run_id = uuid.uuid4()
    event = _event(ledger=LedgerRef(LedgerType.COMMAND_RUN, run_id))

    await SqlAlchemyActivityRecorder(db_session).record(event)

    row = (
        await db_session.execute(
            text("SELECT ledger_type, ledger_id FROM activities WHERE subject_attio_id = :id"),
            {"id": event.subject_attio_id},
        )
    ).one()
    assert (row.ledger_type, row.ledger_id) == ("command_run", run_id)


async def test_an_event_without_a_ledger_stores_nulls(db_session: AsyncSession) -> None:
    event = _event()

    await SqlAlchemyActivityRecorder(db_session).record(event)

    row = (
        await db_session.execute(
            text("SELECT ledger_type, ledger_id FROM activities WHERE subject_attio_id = :id"),
            {"id": event.subject_attio_id},
        )
    ).one()
    assert (row.ledger_type, row.ledger_id) == (None, None)


async def test_occurred_at_sets_the_event_time_otherwise_it_defaults_to_now(
    db_session: AsyncSession,
) -> None:
    earlier = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
    dated = _event(occurred_at=earlier)
    undated = _event()
    recorder = SqlAlchemyActivityRecorder(db_session)
    await recorder.record(dated)
    await recorder.record(undated)

    rows = {
        r.subject_attio_id: r.ts
        for r in (
            await db_session.execute(
                text(
                    "SELECT subject_attio_id, ts FROM activities WHERE subject_attio_id = ANY(:ids)"
                ),
                {"ids": [dated.subject_attio_id, undated.subject_attio_id]},
            )
        ).all()
    }
    assert rows[dated.subject_attio_id] == earlier
    assert rows[undated.subject_attio_id] > earlier


@dataclass(frozen=True)
class _UnknownPayload:
    kind: str = "not-in-the-union"


async def test_a_serialization_bug_is_not_swallowed(db_session: AsyncSession) -> None:
    """Only database errors are swallowed; a programming error must surface in tests."""
    event = _event(payload=_UnknownPayload())  # type: ignore[arg-type]

    with pytest.raises(ValueError):
        await SqlAlchemyActivityRecorder(db_session).record(event)
