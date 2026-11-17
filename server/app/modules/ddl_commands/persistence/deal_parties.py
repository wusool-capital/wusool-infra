"""Read-only list of every live Deal's buyer and seller, for modules that roll mail up to Deals."""

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Deal


@dataclass(frozen=True)
class DealPartyIds:
    """One live Deal with the buyer and seller the mirror holds, as stored."""

    attio_id: str
    buyer_person_attio_id: str | None
    buyer_organization_attio_id: str | None
    seller_organization_attio_id: str | None


async def list_live_deal_parties(session: AsyncSession) -> list[DealPartyIds]:
    rows = await session.execute(
        select(
            Deal.attio_id,
            Deal.buyer_person_attio_id,
            Deal.buyer_organization_attio_id,
            Deal.seller_organization_attio_id,
        ).where(Deal.removed_at.is_(None))
    )
    return [DealPartyIds(*row) for row in rows]
