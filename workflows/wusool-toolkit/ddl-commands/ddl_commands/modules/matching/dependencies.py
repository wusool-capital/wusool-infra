"""Session-managed entry point for the match-count read used by the
`/remove-seller`/`/remove-buyer` confirmation step.
"""

from ddl_commands.modules.matching.infrastructure.match_count_repository import MatchCountRepository
from ddl_commands.shared.database import get_sessionmaker


async def count_match_results_for_buyer(buyer_role_id: str) -> int:
    async with get_sessionmaker()() as session:
        return await MatchCountRepository(session).count_by_buyer_role(buyer_role_id)


async def count_match_results_for_seller(seller_role_id: str) -> int:
    async with get_sessionmaker()() as session:
        return await MatchCountRepository(session).count_by_seller_role(seller_role_id)
