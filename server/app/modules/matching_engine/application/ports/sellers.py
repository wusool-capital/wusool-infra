"""The persistence interface for the sellers concept — implemented by
`persistence/repositories/sellers_repository.py`. Application code never
imports the concrete repository or `app.models` directly — every method
returns `SellerCandidate` (domain), mapped from the ORM row inside the
concrete repository.
"""

from typing import Protocol

from app.modules.matching_engine.domain.sellers import SellerCandidate


class SellerRepositoryPort(Protocol):
    async def get_by_id(self, seller_role_id: str) -> SellerCandidate | None: ...
    async def get_with_organization(self, seller_role_id: str) -> SellerCandidate | None: ...
    async def get_eligible_sellers(
        self, limit: int = 50, offset: int = 0
    ) -> list[SellerCandidate]: ...
    async def get_structured_fields(self, seller_role_id: str) -> SellerCandidate | None: ...
