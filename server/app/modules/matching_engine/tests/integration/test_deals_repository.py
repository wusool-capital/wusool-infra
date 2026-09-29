import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, Deal, SellerRole
from app.modules.matching_engine.domain.matching.deals import DealRecord
from app.modules.matching_engine.persistence.repositories.deals_repository import DealRepository
from app.modules.matching_engine.persistence.repositories.matching_repository import (
    MatchResultRepository,
)


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

    await repo.upsert(_record(any_buyer_role, any_seller_role, "Inbound"))
    await repo.upsert(_record(any_buyer_role, any_seller_role, "Qualified"))

    rows = (await db_session.execute(select(Deal).where(Deal.attio_id == "deal-wp5-test"))).all()
    assert len(rows) == 1
    assert rows[0][0].stage == "Qualified"
    assert rows[0][0].seller_organization_attio_id == any_seller_role.org_attio_id


async def test_update_status_stamps_deal_attio_id(
    db_session: AsyncSession, any_buyer_role: BuyerRole, any_seller_role: SellerRole
) -> None:
    await DealRepository(db_session).upsert(_record(any_buyer_role, any_seller_role, "Qualified"))
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
