import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from wusool_db.models import BuyerRole, SellerRole

from app.modules.matching.infrastructure.repositories import (
    MatchResultRepository,
    MatchScoreRepository,
)


async def test_create_and_retrieve_match_score(
    db_session: AsyncSession, any_buyer_role: BuyerRole, any_seller_role: SellerRole
) -> None:
    repo = MatchScoreRepository(db_session)
    created = await repo.create_many(
        [
            {
                "buyer_attio_id": any_buyer_role.org_attio_id,
                "seller_attio_id": any_seller_role.org_attio_id,
                "score": 87.5,
                "dims": {"strategy": 90, "size": 85},
                "reasoning": "test row, rolled back at teardown",
                "citations": [],
            }
        ]
    )
    assert len(created) == 1

    scores = await repo.get_scores_for_buyer(any_buyer_role.org_attio_id)
    assert any(s.id == created[0].id for s in scores)


async def test_status_transition_is_compare_and_set(
    db_session: AsyncSession, any_buyer_role: BuyerRole, any_seller_role: SellerRole
) -> None:
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

    first = await repo.update_status(
        candidates[0].id,
        expected_status="PENDING_REVIEW",
        status="APPROVED",
        approved_by="U_FIRST",
    )
    second = await repo.update_status(
        candidates[0].id,
        expected_status="PENDING_REVIEW",
        status="REJECTED",
        approved_by="U_SECOND",
    )

    assert first is not None
    assert second is None
    persisted = await repo.get_by_id(candidates[0].id)
    assert persisted is not None
    assert persisted.status == "APPROVED"
