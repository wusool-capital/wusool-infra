"""In-memory `LinkedInHistoryUnitOfWork` for tests: repositories backed by one
shared store, so a second scan sees what the first one stored.
"""

import uuid
from collections.abc import Sequence
from datetime import datetime
from types import TracebackType

from app.modules.activities import ActivityEvent
from app.modules.enrichment.application.ports.linkedin_unit_of_work import (
    LinkedInHistoryUnitOfWorkFactory,
)
from app.modules.enrichment.domain.linkedin import (
    JobChange,
    LinkedInPost,
    ScanRecord,
    job_change_key,
)


class FakeLinkedInHistoryStore:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.error = error
        self.scans: list[ScanRecord] = []
        self.scan_ids: list[uuid.UUID] = []
        self.signal_ids: set[str] = set()
        self.events: list[ActivityEvent] = []
        self.enter_attempts = 0
        self.committed = 0
        self.rolled_back = 0

    def factory(self) -> LinkedInHistoryUnitOfWorkFactory:
        return lambda: _FakeUnitOfWork(self)


class _ScanRepository:
    def __init__(self, store: FakeLinkedInHistoryStore) -> None:
        self._store = store

    async def add(self, record: ScanRecord) -> uuid.UUID:
        scan_id = uuid.uuid4()
        self._store.scans.append(record)
        self._store.scan_ids.append(scan_id)
        return scan_id


class _SignalRepository:
    def __init__(self, store: FakeLinkedInHistoryStore) -> None:
        self._store = store

    async def add_new(
        self,
        *,
        org_attio_id: str,
        scan_id: uuid.UUID,
        posts: Sequence[LinkedInPost],
        job_changes: Sequence[JobChange],
        now: datetime,
    ) -> set[str]:
        ids = [p.external_id for p in posts] + [job_change_key(c) for c in job_changes]
        new = {i for i in ids if i not in self._store.signal_ids}
        self._store.signal_ids |= new
        return new


class _ActivityRecorder:
    def __init__(self, store: FakeLinkedInHistoryStore) -> None:
        self._store = store

    async def record(self, event: ActivityEvent) -> None:
        self._store.events.append(event)


class _FakeUnitOfWork:
    def __init__(self, store: FakeLinkedInHistoryStore) -> None:
        self._store = store
        self.scans = _ScanRepository(store)
        self.signals = _SignalRepository(store)
        self.activities = _ActivityRecorder(store)

    async def __aenter__(self) -> "_FakeUnitOfWork":
        self._store.enter_attempts += 1
        if self._store.error:
            raise self._store.error
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        if exc_type is None:
            self._store.committed += 1
        else:
            self._store.rolled_back += 1
