"""Ports for the deal an approval creates: the Attio write and the Postgres row."""

from typing import Protocol

from app.modules.matching_engine.domain.matching.deals import (
    DealRecord,
    ExistingDeal,
    QualifiedDealDraft,
)


class DealGatewayPort(Protocol):
    async def find_pair_deals(
        self, *, buyer_attio_id: str, seller_attio_id: str
    ) -> list[ExistingDeal]: ...
    async def create_qualified(self, draft: QualifiedDealDraft) -> ExistingDeal: ...
    async def promote_to_qualified(self, deal_attio_id: str) -> None: ...


class DealRepositoryPort(Protocol):
    async def upsert(self, deal: DealRecord) -> None: ...
