"""Concrete `LinkedInHistoryUnitOfWork`: one session per `async with` block,
repositories bound to it, commit on clean exit and rollback on exception —
the same semantics as `ddl_commands`' and `matching_engine`' units of work.
"""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.activities import SqlAlchemyActivityRecorder
from app.modules.enrichment.application.ports.linkedin_unit_of_work import (
    LinkedInHistoryUnitOfWork,
)
from app.modules.enrichment.persistence.repositories.scan_repository import ScanRepository
from app.modules.enrichment.persistence.repositories.signal_repository import SignalRepository


class SqlAlchemyLinkedInUnitOfWork:
    scans: ScanRepository
    signals: SignalRepository
    activities: SqlAlchemyActivityRecorder

    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> LinkedInHistoryUnitOfWork:
        self._session = self._sessionmaker()
        await self._session.__aenter__()
        self.scans = ScanRepository(self._session)
        self.signals = SignalRepository(self._session)
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
