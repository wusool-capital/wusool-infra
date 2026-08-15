"""Read-only, minimal slice of `match_results` — just enough to count how
many match records reference a given buyer/seller role, for the
`/remove-seller`/`/remove-buyer` confirmation step. This bot has no matching
pipeline of its own and doesn't need matching-engine's full `match_results`
ORM model (20+ columns, narrative fields, a status machine) — a plain SQL
count is all that's needed here, so this deliberately isn't an ORM model.
"""

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession


class MatchCountRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def count_by_buyer_role(self, buyer_role_id: str) -> int:
        # `rank IS NOT NULL` excludes the one run/header row that also
        # carries this buyer_role_id (matching-engine's match_results schema:
        # `rank IS NULL` means "run header", not a candidate row) — only
        # actual candidate rows should count as "matches".
        stmt = text(
            "SELECT count(*) FROM match_results WHERE buyer_role_id = :id AND rank IS NOT NULL"
        )
        result = await self._session.execute(stmt, {"id": buyer_role_id})
        return result.scalar_one()

    async def count_by_seller_role(self, seller_role_id: str) -> int:
        stmt = text(
            "SELECT count(*) FROM match_results WHERE seller_role_id = :id AND rank IS NOT NULL"
        )
        result = await self._session.execute(stmt, {"id": seller_role_id})
        return result.scalar_one()
