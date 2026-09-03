"""Unit-of-Work seam for write use cases that need several repositories
together within one transaction (`RunBuyerSellerMatchUseCase`,
`ApproveMatchUseCase`/`RejectMatchUseCase`) — replaces each one constructing
`MatchResultRepository`/`MatchScoreRepository`/`MeetingRepository` directly
off a raw `sessionmaker`, which was a documented, deliberate exception to
"application never imports persistence directly." `MatchingUnitOfWorkFactory`
is what a use case actually takes as a constructor argument, since
`RunBuyerSellerMatchUseCase` specifically needs to open several independent
short-lived transactions within one method, not just one.
"""

from types import TracebackType
from typing import Protocol

from app.modules.matching_engine.application.ports.matching import (
    MatchResultRepositoryPort,
    MatchScoreRepositoryPort,
)
from app.modules.matching_engine.application.ports.meetings import MeetingRepositoryPort


class MatchingUnitOfWork(Protocol):
    # Read-only properties, not plain attributes: a Protocol's plain
    # attribute is invariant (accepts writes of exactly that type), which
    # would reject a concrete class whose attribute is typed as the
    # concrete repository, a subtype of the Port. A property has no such
    # constraint — only the getter's return type needs to be compatible.
    @property
    def match_results(self) -> MatchResultRepositoryPort: ...
    @property
    def match_scores(self) -> MatchScoreRepositoryPort: ...
    @property
    def meetings(self) -> MeetingRepositoryPort: ...

    async def __aenter__(self) -> "MatchingUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class MatchingUnitOfWorkFactory(Protocol):
    def __call__(self) -> MatchingUnitOfWork: ...
