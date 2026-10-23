"""Concrete `DdlCommandsUnitOfWork`: opens one session per `async with`
block, builds the repositories bound to it, commits on clean exit or
rolls back on exception — the same semantics `async with session.begin():`
gave each write use case before, now factored out instead of each one
constructing `BuyerRepository`/`SellerRepository`/`OrganizationRepository`
directly off a raw `sessionmaker`.
"""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.activities import SqlAlchemyActivityRecorder
from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWork
from app.modules.ddl_commands.persistence.repositories.buyers_repository import BuyerRepository
from app.modules.ddl_commands.persistence.repositories.command_runs_repository import (
    CommandRunRepository,
)
from app.modules.ddl_commands.persistence.repositories.sellers_repository import SellerRepository
from app.modules.organizations import OrganizationRepository


class SqlAlchemyDdlCommandsUnitOfWork:
    buyers: BuyerRepository
    sellers: SellerRepository
    organizations: OrganizationRepository
    command_runs: CommandRunRepository
    activities: SqlAlchemyActivityRecorder

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> DdlCommandsUnitOfWork:
        self._session = self._sessionmaker()
        await self._session.__aenter__()
        self.buyers = BuyerRepository(self._session)
        self.sellers = SellerRepository(self._session)
        self.organizations = OrganizationRepository(self._session)
        self.command_runs = CommandRunRepository(self._session)
        self.activities = SqlAlchemyActivityRecorder(self._session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        assert self._session is not None
        try:
            if exc_type is None:
                await self._session.commit()
            else:
                await self._session.rollback()
        finally:
            await self._session.__aexit__(exc_type, exc, tb)
