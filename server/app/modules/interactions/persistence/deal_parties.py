"""Implements `DealPartiesPort` through the module that owns the `deals` table."""

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ddl_commands import list_live_deal_parties
from app.modules.interactions.domain.deals import DealParties


class SqlAlchemyDealParties:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def load(self) -> tuple[DealParties, ...]:
        async with self._sessionmaker() as session:
            deals = await list_live_deal_parties(session)
        return tuple(
            DealParties(
                d.attio_id,
                d.buyer_person_attio_id,
                d.buyer_organization_attio_id,
                d.seller_organization_attio_id,
            )
            for d in deals
        )
