"""One sweep pass. The ceilings themselves are enforced in SQL and covered
in `tests/integration/test_tool_runs_repository.py`; this covers what the
pass does with what the repository hands back.
"""

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.modules.lead_magnets.application.sweeper import sweep_once
from app.modules.lead_magnets.domain.tool_run import Tool, ToolRunRecord


def _record(tool: Tool = "valuation", stage: str | None = "attio") -> ToolRunRecord:
    return ToolRunRecord(
        id=uuid4(), tool=tool, status="failed", attempt_count=2, payload={}, stage=stage
    )


class _FakePort:
    def __init__(self, *, claimed=(), abandoned=(), promoted=0) -> None:
        self._claimed = list(claimed)
        self._abandoned = list(abandoned)
        self._promoted = promoted
        self.cutoffs: list[datetime] = []
        self.promote_calls = 0

    async def promote_role_fks(self) -> int:
        self.promote_calls += 1
        return self._promoted

    async def abandon_past_ceiling(self, *, cutoff):
        self.cutoffs.append(cutoff)
        return self._abandoned

    async def claim_stale(self, *, cutoff):
        self.cutoffs.append(cutoff)
        return self._claimed


class _FakeSubmissions:
    def __init__(self) -> None:
        self.completed: list[UUID] = []

    async def complete(self, run) -> None:
        self.completed.append(run.id)


async def test_sweep_resumes_every_claimed_run() -> None:
    runs = [_record(), _record("benchmark")]
    port, submissions = _FakePort(claimed=runs), _FakeSubmissions()

    assert await sweep_once(port, submissions, stale_after_s=300) == 2
    assert submissions.completed == [r.id for r in runs]


async def test_sweep_promotes_role_fks_every_pass() -> None:
    """The mirror lands role rows after `finish` ran, so the FK back-fill has
    to be part of the routine pass, not a one-off."""
    port, submissions = _FakePort(promoted=3), _FakeSubmissions()
    await sweep_once(port, submissions, stale_after_s=300)
    assert port.promote_calls == 1


async def test_abandoned_runs_are_not_resumed() -> None:
    """Past its ceiling means a human is needed — resuming it would just
    burn another attempt."""
    port, submissions = _FakePort(abandoned=[_record("readiness", "ai")]), _FakeSubmissions()
    assert await sweep_once(port, submissions, stale_after_s=300) == 0
    assert submissions.completed == []


async def test_cutoff_is_in_the_past_by_the_stale_window() -> None:
    port, submissions = _FakePort(), _FakeSubmissions()
    before = datetime.now(UTC)
    await sweep_once(port, submissions, stale_after_s=600)
    assert port.cutoffs, "the pass must ask the repository for stale rows"
    assert all((before - c).total_seconds() >= 599 for c in port.cutoffs)
