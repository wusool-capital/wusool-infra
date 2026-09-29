"""Implements `discrepancies.BuyerCriteriaReaderPort` by reusing this
module's own buyer search/lookup — `/check-buyer` and `/find-match` search
the same buyers by the same rules, with no second copy of that logic. The
reverse of `discovery.SellerDraftPort`'s hand-off: here it's this module
implementing another's Port, not the other way round.
"""

from app.modules.discrepancies import BuyerCriteria
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.persistence.repositories.buyers_repository import BuyerRepository


def to_buyer_criteria(context: BuyerContext) -> BuyerCriteria:
    return BuyerCriteria(
        buyer_role_id=context.buyer_role_id,
        org_name=context.org_name,
        target_vertical=context.target_vertical,
        org_hq_country=context.org_hq_country,
        target_region=context.target_region,
        target_country=context.target_country,
        check_size_min=context.check_size_min.amount if context.check_size_min else None,
        check_size_max=context.check_size_max.amount if context.check_size_max else None,
        ebitda_floor=context.ebitda_floor.amount if context.ebitda_floor else None,
        ebitda_ceiling=context.ebitda_ceiling.amount if context.ebitda_ceiling else None,
    )


class MatchingEngineCriteriaReaderAdapter:
    async def search(self, name: str) -> list[BuyerCriteria]:
        async with get_sessionmaker()() as session:
            contexts = await BuyerRepository(session).search_by_organization_name(name)
        return [to_buyer_criteria(c) for c in contexts]

    async def get(self, buyer_role_id: str) -> BuyerCriteria | None:
        async with get_sessionmaker()() as session:
            context = await BuyerRepository(session).get_with_organization(buyer_role_id)
        return to_buyer_criteria(context) if context else None
