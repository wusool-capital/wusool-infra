"""Preview and commit state for bulk uploads, behind `PreviewStore` so a
Postgres adapter can replace the in-memory one without touching callers.

The in-memory adapter is process-local: a restart forgets every preview. That
is safe, because each row is re-checked against the database before it is
added, so a rerun after a restart never duplicates.
"""

import time
import uuid
from collections.abc import Callable
from typing import Literal, Protocol

from pydantic import BaseModel, ConfigDict

from app.modules.ddl_commands.api.schemas import PrefillValue

UploadKind = Literal["buyer", "seller"]
CommitState = Literal["ready", "running", "done", "interrupted"]
OutcomeKind = Literal["added", "skipped", "failed"]

MAX_ROWS = 1_000
PREVIEW_TTL_SECONDS = 3_600
# Bounds memory; a preview is only useful for the one conversation that made it.
_MAX_STORED = 50


class PlannedRow(BaseModel):
    """One valid row that was new at preview time. Field names match the Slack
    add forms, split into organization and role fields."""

    model_config = ConfigDict(frozen=True)

    index: int  # 1-based position in the uploaded list
    org_name: str
    domain: str  # full host, lower-case, no "www."; a subdomain is a different domain
    org_extracted: dict[str, PrefillValue | None]
    role_extracted: dict[str, PrefillValue | None]


class StoredPreview(BaseModel):
    model_config = ConfigDict(frozen=True)

    id: uuid.UUID
    kind: UploadKind
    rows: tuple[PlannedRow, ...]


class RowOutcome(BaseModel):
    model_config = ConfigDict(frozen=True)

    row: int
    kind: OutcomeKind
    reason: str | None = None


class CommitProgress(BaseModel):
    model_config = ConfigDict(frozen=True)

    state: CommitState
    total: int
    added: int = 0
    skipped: tuple[RowOutcome, ...] = ()
    failed: tuple[RowOutcome, ...] = ()

    def record(self, outcome: RowOutcome) -> "CommitProgress":
        if outcome.kind == "added":
            return self.model_copy(update={"added": self.added + 1})
        if outcome.kind == "skipped":
            return self.model_copy(update={"skipped": (*self.skipped, outcome)})
        return self.model_copy(update={"failed": (*self.failed, outcome)})


class PreviewStore(Protocol):
    def save(self, preview: StoredPreview) -> None: ...

    def get(self, preview_id: uuid.UUID) -> StoredPreview | None: ...

    def progress(self, preview_id: uuid.UUID) -> CommitProgress | None: ...

    def set_progress(self, preview_id: uuid.UUID, progress: CommitProgress) -> None: ...


class _Entry(BaseModel):
    model_config = ConfigDict(frozen=True)

    preview: StoredPreview
    progress: CommitProgress
    expires_at: float


class InMemoryPreviewStore:
    def __init__(
        self,
        *,
        ttl_seconds: float = PREVIEW_TTL_SECONDS,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._ttl = ttl_seconds
        self._clock = clock
        self._entries: dict[uuid.UUID, _Entry] = {}

    def save(self, preview: StoredPreview) -> None:
        self._evict()
        self._entries[preview.id] = _Entry(
            preview=preview,
            progress=CommitProgress(state="ready", total=len(preview.rows)),
            expires_at=self._clock() + self._ttl,
        )
        while len(self._entries) > _MAX_STORED:
            # A running commit must stay readable, or its caller loses the results.
            oldest_idle = next(
                (k for k, e in self._entries.items() if e.progress.state != "running"), None
            )
            if oldest_idle is None:
                break
            del self._entries[oldest_idle]

    def get(self, preview_id: uuid.UUID) -> StoredPreview | None:
        entry = self._live(preview_id)
        return entry.preview if entry else None

    def progress(self, preview_id: uuid.UUID) -> CommitProgress | None:
        entry = self._live(preview_id)
        return entry.progress if entry else None

    def set_progress(self, preview_id: uuid.UUID, progress: CommitProgress) -> None:
        entry = self._live(preview_id)
        if entry is None:
            return
        # Each write extends the life, so a long commit never expires mid-run.
        self._entries[preview_id] = entry.model_copy(
            update={"progress": progress, "expires_at": self._clock() + self._ttl}
        )

    def _live(self, preview_id: uuid.UUID) -> _Entry | None:
        entry = self._entries.get(preview_id)
        if entry is not None and entry.expires_at <= self._clock():
            del self._entries[preview_id]
            return None
        return entry

    def _evict(self) -> None:
        now = self._clock()
        for key in [k for k, e in self._entries.items() if e.expires_at <= now]:
            del self._entries[key]
