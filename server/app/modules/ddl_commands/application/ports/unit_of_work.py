"""Unit-of-Work seam for write use cases that touch more than one repository
in one transaction (`DdlCommandsService`'s `update_buyer`/`create_buyer`,
`update_seller`/`create_seller` — each also writes the parent
`organizations` row) — replaces each one constructing `BuyerRepository`/
`SellerRepository`/`OrganizationRepository` directly off a raw
`sessionmaker`, mirroring `matching_engine`'s own `MatchingUnitOfWork`.
"""

from types import TracebackType
from typing import Protocol

from app.modules.ddl_commands.application.ports.buyers import BuyerRepositoryPort
from app.modules.ddl_commands.application.ports.sellers import SellerRepositoryPort
from app.modules.organizations import OrganizationRepositoryPort


class DdlCommandsUnitOfWork(Protocol):
    # Read-only properties, not plain attributes — see the identical note
    # in matching_engine's own `MatchingUnitOfWork`.
    @property
    def buyers(self) -> BuyerRepositoryPort: ...
    @property
    def sellers(self) -> SellerRepositoryPort: ...
    @property
    def organizations(self) -> OrganizationRepositoryPort: ...

    async def __aenter__(self) -> "DdlCommandsUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class DdlCommandsUnitOfWorkFactory(Protocol):
    def __call__(self) -> DdlCommandsUnitOfWork: ...
