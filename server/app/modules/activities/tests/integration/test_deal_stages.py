import uuid

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.activities import ActivityActor, ActivitySource, SqlAlchemyDealStageRecorder


async def _seed_deal(session: AsyncSession, stage: str | None) -> str:
    deal_id = f"deal-{uuid.uuid4()}"
    await session.execute(
        text("INSERT INTO deals(attio_id, name, stage) VALUES (:id, 'D', :stage)"),
        {"id": deal_id, "stage": stage},
    )
    return deal_id


async def _record(
    recorder: SqlAlchemyDealStageRecorder, deal_id: str, previous: str | None, new: str | None
) -> uuid.UUID | None:
    return await recorder.record_change(
        deal_attio_id=deal_id,
        previous_stage=previous,
        new_stage=new,
        actor=ActivityActor.slack("U1"),
        source=ActivitySource.MATCHING_ENGINE,
    )


async def test_current_stage_reads_the_stored_stage(db_session: AsyncSession) -> None:
    deal_id = await _seed_deal(db_session, "Inbound")
    recorder = SqlAlchemyDealStageRecorder(db_session)

    assert await recorder.current_stage(deal_id) == "Inbound"
    assert await recorder.current_stage("no-such-deal") is None


async def test_a_stage_change_writes_the_event_and_a_linked_activity(
    db_session: AsyncSession,
) -> None:
    deal_id = await _seed_deal(db_session, "Qualified")
    recorder = SqlAlchemyDealStageRecorder(db_session)

    event_id = await _record(recorder, deal_id, "Inbound", "Qualified")

    event = (
        await db_session.execute(
            text("SELECT from_stage, to_stage, source FROM deal_stage_events WHERE id = :id"),
            {"id": event_id},
        )
    ).one()
    assert (event.from_stage, event.to_stage, event.source) == (
        "Inbound",
        "Qualified",
        "matching_engine",
    )
    activity = (
        await db_session.execute(
            text(
                "SELECT event_type, subject_type, subject_attio_id, actor_type, payload "
                "FROM activities WHERE deal_stage_event_id = :id"
            ),
            {"id": event_id},
        )
    ).one()
    assert (activity.event_type, activity.subject_type) == ("deal.stage_changed", "Deal")
    assert activity.subject_attio_id == deal_id
    assert activity.actor_type == "slack_user"
    assert activity.payload == {
        "kind": "stage_change",
        "from_stage": "Inbound",
        "to_stage": "Qualified",
    }


async def test_a_new_deal_records_a_change_from_nothing(db_session: AsyncSession) -> None:
    deal_id = await _seed_deal(db_session, "Inbound")
    recorder = SqlAlchemyDealStageRecorder(db_session)

    assert await _record(recorder, deal_id, None, "Inbound") is not None


async def test_no_change_and_no_new_stage_record_nothing(db_session: AsyncSession) -> None:
    deal_id = await _seed_deal(db_session, "Qualified")
    recorder = SqlAlchemyDealStageRecorder(db_session)

    assert await _record(recorder, deal_id, "Qualified", "Qualified") is None
    assert await _record(recorder, deal_id, "Qualified", None) is None
    count = (
        await db_session.execute(
            text("SELECT count(*) FROM deal_stage_events WHERE deal_attio_id = :id"),
            {"id": deal_id},
        )
    ).scalar_one()
    assert count == 0
