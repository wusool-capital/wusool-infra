"""Concrete `MatchingUnitOfWork`: opens one session per `async with` block,
builds the three repositories bound to it, commits on clean exit or rolls
back on exception — the same commit-on-success/rollback-on-exception
semantics `async with session.begin():` gave the one block of
`run_match` that used it, now uniform across every block
(a plain commit on a session with no pending writes, for the read-only
blocks, is a no-op).
"""

from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.matching_engine.application.ports.unit_of_work import MatchingUnitOfWork
from app.modules.matching_engine.persistence.repositories.matching_repository import (
    MatchResultRepository,
    MatchScoreRepository,
)
from app.modules.matching_engine.persistence.repositories.meetings_repository import (
    MeetingRepository,
)


class SqlAlchemyMatchingUnitOfWork:
    match_results: MatchResultRepository
    match_scores: MatchScoreRepository
    meetings: MeetingRepository

    def __init__(
        self, sessionmaker: async_sessionmaker[AsyncSession], *, meeting_notes_max_chars: int = 600
    ) -> None:
        self._sessionmaker = sessionmaker
        self._meeting_notes_max_chars = meeting_notes_max_chars
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> MatchingUnitOfWork:
        self._session = self._sessionmaker()
        await self._session.__aenter__()
        self.match_results = MatchResultRepository(self._session)
        self.match_scores = MatchScoreRepository(self._session)
        self.meetings = MeetingRepository(self._session, max_chars=self._meeting_notes_max_chars)
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
