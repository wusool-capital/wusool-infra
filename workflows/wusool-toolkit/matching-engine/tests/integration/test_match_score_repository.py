from sqlalchemy.ext.asyncio import AsyncSession
from wusool_db.models import BuyerRole, SellerRole

from app.modules.matching.infrastructure.repositories import MatchScoreRepository


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
