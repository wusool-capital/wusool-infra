"""Deals are read through `ddl_commands`, which owns the table: live ones only."""

from datetime import UTC, datetime

from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Deal, Organization, Person
from app.modules.interactions.domain.deals import DealParties
from app.modules.interactions.persistence.deal_parties import SqlAlchemyDealParties


async def test_live_deals_come_back_with_their_buyer_and_seller(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    seller, buyer = f"{record_prefix}o", f"{record_prefix}p"
    live, removed = f"{record_prefix}d1", f"{record_prefix}d2"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=seller, name="Acme"))
        session.add(Person(attio_id=buyer, name="Bob"))
        await session.flush()
        session.add(
            Deal(
                attio_id=live,
                name="Live",
                seller_organization_attio_id=seller,
                buyer_person_attio_id=buyer,
            )
        )
        session.add(Deal(attio_id=removed, name="Gone", removed_at=datetime.now(UTC)))
    try:
        deals = {d.deal_id: d for d in await SqlAlchemyDealParties(sessionmaker).load()}

        assert deals[live] == DealParties(live, buyer, None, seller)
        assert removed not in deals
    finally:
        # The fixture removes the Person and Organization, which the Deals still point at.
        async with sessionmaker() as session, session.begin():
            await session.execute(delete(Deal).where(Deal.attio_id.in_([live, removed])))
