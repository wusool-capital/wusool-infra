"""The persistence interface `application/buyers.py` depends on — implemented
by `persistence/repositories/buyers_repository.py`. Application code never
imports the concrete repository or `app.models` directly — every method
returns `BuyerContext` (domain), mapped from the ORM row inside the
concrete repository.
"""

from typing import Protocol

from app.modules.matching_engine.domain.buyers import BuyerContext


class BuyerRepositoryPort(Protocol):
    async def get_by_id(self, buyer_role_id: str) -> BuyerContext | None: ...
    async def get_with_organization(self, buyer_role_id: str) -> BuyerContext | None: ...
    async def search_by_organization_name(
        self, term: str, limit: int = 10
    ) -> list[BuyerContext]: ...
    async def get_requirement_profile(self, buyer_role_id: str) -> BuyerContext | None: ...
