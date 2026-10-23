"""Unit-of-Work seam for the LinkedIn scan history: a scan run, its signals
and its activity are written in one transaction, so they use one session.
Mirrors `ddl_commands`' and `matching_engine`'s own units of work.
"""

from collections.abc import Sequence
from datetime import datetime
from types import TracebackType
from typing import Protocol
from uuid import UUID

from app.modules.activities import ActivityRecorderPort
from app.modules.enrichment.domain.linkedin import JobChange, LinkedInPost, ScanRecord


class ScanRepositoryPort(Protocol):
    async def add(self, record: ScanRecord) -> UUID:
        """Stores one scan (succeeded or failed) and returns its id."""
        ...


class SignalRepositoryPort(Protocol):
    async def add_new(
        self,
        *,
        org_attio_id: str,
        scan_id: UUID,
        posts: Sequence[LinkedInPost],
        job_changes: Sequence[JobChange],
        now: datetime,
    ) -> set[str]:
        """Stores each post and job change not stored before, and returns the
        external ids of the ones that were new."""
        ...


class LinkedInHistoryUnitOfWork(Protocol):
    # Read-only properties, not plain attributes — see the identical note
    # in `matching_engine`'s `MatchingUnitOfWork`.
    @property
    def scans(self) -> ScanRepositoryPort: ...
    @property
    def signals(self) -> SignalRepositoryPort: ...
    @property
    def activities(self) -> ActivityRecorderPort: ...

    async def __aenter__(self) -> "LinkedInHistoryUnitOfWork": ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...


class LinkedInHistoryUnitOfWorkFactory(Protocol):
    def __call__(self) -> LinkedInHistoryUnitOfWork: ...
