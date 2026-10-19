import uuid
from collections.abc import Mapping

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    ActorType,
    EventType,
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


async def test_failed_insert_is_swallowed_and_keeps_the_transaction(
    db_session: AsyncSession,
) -> None:
    org_id = f"org-{uuid.uuid4()}"
    await _seed_org(db_session, org_id)
    recorder = SqlAlchemyActivityRecorder(db_session)

    # A command_run_id with no matching ledger row violates the FK.
    await recorder.record(_event(command_run_id=uuid.uuid4()))

    # The caller's transaction is still usable and its earlier work survives.
    await recorder.record(_event(subject_attio_id=org_id))
    org_count = (
        await db_session.execute(
            text("SELECT count(*) FROM organizations WHERE attio_id = :id"), {"id": org_id}
        )
    ).scalar_one()
    assert org_count == 1
    assert await _count(db_session, "subject_attio_id = :id", id=org_id) == 1
