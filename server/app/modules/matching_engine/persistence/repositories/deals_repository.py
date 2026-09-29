"""Writes the `deals` row an approval creates. Like the other repositories,
it only flushes — the unit of work owns commit/rollback."""

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.deal import Deal
from app.modules.matching_engine.domain.matching.deals import DealRecord


class DealRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def upsert(self, deal: DealRecord) -> None:
        # ON CONFLICT: the inbound Attio webhook may have synced this deal
        # before the approval commits.
        stmt = insert(Deal).values(
            attio_id=deal.attio_id,
            name=deal.name,
            stage=deal.stage,
            buyer_organization_attio_id=deal.buyer_attio_id,
            seller_organization_attio_id=deal.seller_attio_id,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=[Deal.attio_id],
            # An unstaged deal must not blank a stage the sync already stored.
            set_={
                "stage": func.coalesce(stmt.excluded.stage, Deal.stage),
                "updated_at": func.now(),
                "removed_at": None,
            },
        )
        await self._session.execute(stmt)
        await self._session.flush()
