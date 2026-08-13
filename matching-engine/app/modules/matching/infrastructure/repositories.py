"""Match-score persistence. `add()`/`flush()`/`execute()` only — never
`commit()` or `rollback()`; the caller owns the transaction boundary.

No `match_runs`/`matches`/`match_evidence` here — those tables don't exist
(see the module docstring in `models.py`).
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.matching.infrastructure.models import MatchScore


class MatchScoreRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, rows: list[dict]) -> list[MatchScore]:
        """`rows` are plain kwargs dicts for `MatchScore` (buyer_attio_id,
        seller_attio_id, score, dims, reasoning, citations). Flushes only —
        does not commit.
        """
        scores = [MatchScore(**row) for row in rows]
        self._session.add_all(scores)
        await self._session.flush()
        return scores

    async def get_scores_for_buyer(self, buyer_attio_id: str, limit: int = 50) -> list[MatchScore]:
        stmt = (
            select(MatchScore)
            .where(MatchScore.buyer_attio_id == buyer_attio_id)
            .order_by(MatchScore.generated_at.desc())
            .limit(limit)
        )
        return list((await self._session.execute(stmt)).scalars().all())

    async def get_latest_score_for_pair(
        self, buyer_attio_id: str, seller_attio_id: str
    ) -> MatchScore | None:
        stmt = (
            select(MatchScore)
            .where(
                MatchScore.buyer_attio_id == buyer_attio_id,
                MatchScore.seller_attio_id == seller_attio_id,
            )
            .order_by(MatchScore.generated_at.desc())
            .limit(1)
        )
        return (await self._session.execute(stmt)).scalar_one_or_none()
