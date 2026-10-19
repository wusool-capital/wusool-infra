import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Deal, SellerRole
from app.modules.activities import ActivityActor
from app.modules.matching_engine.domain.matching.deals import DealRecord
from app.modules.matching_engine.persistence.repositories.deals_repository import DealRepository
from app.modules.matching_engine.persistence.repositories.matching_repository import (
    MatchResultRepository,
)

_ACTOR = ActivityActor.slack("U_TEST")


def _record(buyer: BuyerRole, seller: SellerRole, stage: str) -> DealRecord:
    return DealRecord(
        attio_id="deal-wp5-test",
        name="Seller - Buyer",
        stage=stage,
        buyer_attio_id=buyer.org_attio_id,
        seller_attio_id=seller.org_attio_id,
    )


async def test_upsert_inserts_then_updates_stage(
    db_session: AsyncSession, any_buyer_role: BuyerRole, any_seller_role: SellerRole
) -> None:
    repo = DealRepository(db_session)

    await repo.upsert(_record(any_buyer_role, any_seller_role, "Inbound"), actor=_ACTOR)
    await repo.upsert(_record(any_buyer_role, any_seller_role, "Qualified"), actor=_ACTOR)

    rows = (await db_session.execute(select(Deal).where(Deal.attio_id == "deal-wp5-test"))).all()
    assert len(rows) == 1
    assert rows[0][0].stage == "Qualified"
    assert rows[0][0].seller_organization_attio_id == any_seller_role.org_attio_id


async def test_update_status_stamps_deal_attio_id(
    db_session: AsyncSession, any_buyer_role: BuyerRole, any_seller_role: SellerRole
) -> None:
    await DealRepository(db_session).upsert(
        _record(any_buyer_role, any_seller_role, "Qualified"), actor=_ACTOR
    )
    repo = MatchResultRepository(db_session)
    run_id = uuid.uuid4()
    await repo.create_run(
        run_id=run_id,
        buyer_attio_id=any_buyer_role.org_attio_id,
        buyer_role_id=any_buyer_role.id,
        requested_by="test-user",
    )
    candidates = await repo.create_candidates(
        [
            {
                "run_id": run_id,
                "buyer_attio_id": any_buyer_role.org_attio_id,
                "buyer_role_id": any_buyer_role.id,
                "rank": 1,
                "seller_attio_id": any_seller_role.org_attio_id,
                "seller_role_id": any_seller_role.id,
                "status": "PENDING_REVIEW",
            }
        ]
    )

    updated = await repo.update_status(
        uuid.UUID(candidates[0].id),
        expected_status="PENDING_REVIEW",
        status="APPROVED",
        deal_attio_id="deal-wp5-test",
    )

    assert updated is not None
    assert updated.deal_attio_id == "deal-wp5-test"


def _bare_record(deal_id: str, stage: str | None) -> DealRecord:
    return DealRecord(
        attio_id=deal_id,
        name="Seller - Buyer",
        stage=stage,
        buyer_attio_id=None,
        seller_attio_id=None,
    )  # type: ignore[arg-type]


async def _stage_history(db_session: AsyncSession, deal_id: str) -> list[tuple[str | None, str]]:
    rows = (
        await db_session.execute(
            text(
                "SELECT from_stage, to_stage FROM deal_stage_events "
                "WHERE deal_attio_id = :id ORDER BY created_at"
            ),
            {"id": deal_id},
        )
    ).all()
    return [(r.from_stage, r.to_stage) for r in rows]


async def test_upsert_records_each_real_stage_change_with_the_approver(
    db_session: AsyncSession,
) -> None:
    deal_id = f"deal-{uuid.uuid4()}"
    repo = DealRepository(db_session)

    await repo.upsert(_bare_record(deal_id, "Inbound"), actor=_ACTOR)
    await repo.upsert(_bare_record(deal_id, "Qualified"), actor=_ACTOR)

    assert await _stage_history(db_session, deal_id) == [
        (None, "Inbound"),
        ("Inbound", "Qualified"),
    ]
    activity = (
        await db_session.execute(
            text(
                "SELECT actor_ref, source FROM activities "
                "WHERE subject_attio_id = :id AND event_type = 'deal.stage_changed' LIMIT 1"
            ),
            {"id": deal_id},
        )
    ).one()
    assert (activity.actor_ref, activity.source) == ("U_TEST", "matching_engine")


async def test_upsert_records_nothing_when_the_webhook_already_set_the_stage(
    db_session: AsyncSession,
) -> None:
    deal_id = f"deal-{uuid.uuid4()}"
    await db_session.execute(
        text("INSERT INTO deals(attio_id, name, stage) VALUES (:id, 'D', 'Qualified')"),
        {"id": deal_id},
    )

    await DealRepository(db_session).upsert(_bare_record(deal_id, "Qualified"), actor=_ACTOR)

    assert await _stage_history(db_session, deal_id) == []


async def test_an_unstaged_upsert_keeps_the_stored_stage_and_records_nothing(
    db_session: AsyncSession,
) -> None:
    deal_id = f"deal-{uuid.uuid4()}"
    await db_session.execute(
        text("INSERT INTO deals(attio_id, name, stage) VALUES (:id, 'D', 'Diligence')"),
        {"id": deal_id},
    )

    await DealRepository(db_session).upsert(_bare_record(deal_id, None), actor=_ACTOR)

    assert await _stage_history(db_session, deal_id) == []
    stage = (
        await db_session.execute(
            text("SELECT stage FROM deals WHERE attio_id = :id"), {"id": deal_id}
        )
    ).scalar_one()
    assert stage == "Diligence"
