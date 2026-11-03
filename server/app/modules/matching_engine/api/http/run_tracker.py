"""Per-run state the web app shows but `match_results` has no column for: the
advisor-facing run notes and the discovery step's progress.

Process-local on purpose (no schema change in the MVP): a restart forgets it,
and `RunDetailResponse` then falls back to what the persisted rows show.
"""

import uuid
from dataclasses import dataclass, field, replace

from app.modules.matching_engine.api.http.schemas import DiscoveryStatus

# Bounds memory; only the most recent runs are ever polled.
_MAX_TRACKED_RUNS = 500


@dataclass(frozen=True)
class TrackedDiscovery:
    status: DiscoveryStatus
    message: str | None = None
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class TrackedRun:
    notes: tuple[str, ...] = ()
    discovery: TrackedDiscovery | None = None
    # True while this process is matching it, so a slow run never reads as stale.
    executing: bool = False


@dataclass
class RunTracker:
    _runs: dict[uuid.UUID, TrackedRun] = field(default_factory=dict)
    # Client request id -> run it started, so a repeated "Run match" returns the same run.
    _starts: dict[uuid.UUID, uuid.UUID] = field(default_factory=dict)

    def get(self, run_id: uuid.UUID) -> TrackedRun | None:
        return self._runs.get(run_id)

    def set_notes(self, run_id: uuid.UUID, notes: list[str]) -> None:
        self._put(run_id, replace(self._current(run_id), notes=tuple(notes)))

    def set_discovery(self, run_id: uuid.UUID, discovery: TrackedDiscovery) -> None:
        self._put(run_id, replace(self._current(run_id), discovery=discovery))

    def clear_discovery(self, run_id: uuid.UUID) -> None:
        self._put(run_id, replace(self._current(run_id), discovery=None))

    def set_executing(self, run_id: uuid.UUID, executing: bool) -> None:
        self._put(run_id, replace(self._current(run_id), executing=executing))

    def started_run(self, request_id: uuid.UUID) -> uuid.UUID | None:
        return self._starts.get(request_id)

    def remember_start(self, request_id: uuid.UUID, run_id: uuid.UUID) -> None:
        self._starts[request_id] = run_id
        while len(self._starts) > _MAX_TRACKED_RUNS:
            del self._starts[next(iter(self._starts))]

    def _current(self, run_id: uuid.UUID) -> TrackedRun:
        return self._runs.get(run_id, TrackedRun())

    def _put(self, run_id: uuid.UUID, tracked: TrackedRun) -> None:
        self._runs.pop(run_id, None)
        self._runs[run_id] = tracked
        while len(self._runs) > _MAX_TRACKED_RUNS:
            del self._runs[next(iter(self._runs))]


run_tracker = RunTracker()
