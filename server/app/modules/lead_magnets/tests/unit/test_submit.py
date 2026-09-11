"""The write contract's ordering and its resume behaviour.

Fakes for all three network seams — the point of these tests is the order
of operations and what a resume is allowed to repeat, neither of which needs
a real provider.
"""

from dataclasses import asdict
from uuid import UUID, uuid4

import pytest

from app.modules.lead_magnets.application.shared.submit import SubmissionService
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs, Tool, ToolRunRecord
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError

_SUBJECTS = SubjectRefs(org_attio_id="org-1", org_name="Acme", seller_role_entry_id="entry-1")
_NO_SUBJECTS = SubjectRefs()


class _FakeToolRuns:
    """Records every call in order, so a test can assert what happened
    before what."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.started: list[tuple[str, str]] = []
        self.stages: list[tuple[str, JsonObject | None]] = []
        self.finished: list[tuple[str, str | None]] = []
        self.is_new = True

    async def start(self, *, tool, payload, idempotency_key):
        self.calls.append("start")
        self.started.append((tool, idempotency_key))
        return uuid4(), self.is_new

    async def set_stage(self, run_id, *, stage, output=None):
        self.calls.append(f"set_stage:{stage}")
        self.stages.append((stage, output))

    async def finish(self, run_id, status, *, subjects=_NO_SUBJECTS, error=None):
        self.calls.append(f"finish:{status}")
        self.finished.append((status, error))

    async def get(self, run_id):
        return None

    async def claim_stale(self, *, cutoff):
        return []

    async def abandon_past_ceiling(self, *, cutoff):
        return []

    async def promote_role_fks(self):
        return 0


class _FakeAttio:
    def __init__(self, *, fail: bool = False) -> None:
        self.writes = 0
        self._fail = fail

    async def write(self, *, tool, payload, ai):
        self.writes += 1
        if self._fail:
            raise RuntimeError("attio down")
        return _SUBJECTS


def _run(tool: Tool = "valuation", payload: JsonObject | None = None) -> ToolRunRecord:
    return ToolRunRecord(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        tool=tool,
        status="running",
        attempt_count=1,
        payload=payload or {},
        stage=(payload or {}).get("stage"),
    )


def _service(
    tool_runs: _FakeToolRuns,
    attio: _FakeAttio,
    *,
    ai_raises: bool = False,
    fallback: JsonObject | None = None,
) -> tuple[SubmissionService, list[str]]:
    ai_calls: list[str] = []

    async def run_ai(tool: str, payload: JsonObject) -> JsonObject:
        ai_calls.append(tool)
        if ai_raises:
            raise BedrockInvocationError("throttled")
        return {"pros": ["a"]}

    def run_fallback(tool: str, payload: JsonObject) -> JsonObject | None:
        return fallback

    return (
        SubmissionService(tool_runs=tool_runs, attio=attio, run_ai=run_ai, fallback=run_fallback),
        ai_calls,
    )


async def test_record_happens_before_any_provider_call() -> None:
    """Step 1 is the whole design. `record` must touch nothing but the
    ledger."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, ai_calls = _service(tool_runs, attio)

    await service.record(
        tool="readiness",
        payload={"answers": {}},
        email="F@Acme.com",
        domain="https://www.acme.com",
        submission_id="s1",
    )

    assert tool_runs.calls == ["start"]
    assert ai_calls == []
    assert attio.writes == 0
    # The key is normalised, not the raw form input.
    assert tool_runs.started[0] == ("readiness", "readiness|f@acme.com|acme.com|s1")


async def test_record_reports_a_replay_so_the_caller_stops() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    tool_runs.is_new = False
    service, _ = _service(tool_runs, attio)

    _, is_new = await service.record(
        tool="readiness", payload={}, email="f@acme.com", domain="acme.com", submission_id="s1"
    )
    assert is_new is False


async def test_happy_path_order() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, ai_calls = _service(tool_runs, attio)

    await service.complete(_run())

    assert tool_runs.calls == ["set_stage:ai", "set_stage:attio", "finish:succeeded"]
    assert ai_calls == ["valuation"]
    assert attio.writes == 1


async def test_attio_stage_is_recorded_before_finish() -> None:
    """A crash between the two must leave a row that knows Attio is already
    done, or the resume writes Attio twice and duplicates the record."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio)

    await service.complete(_run())

    assert tool_runs.calls.index("set_stage:attio") < tool_runs.calls.index("finish:succeeded")
    stage, output = tool_runs.stages[-1]
    assert stage == "attio"
    assert output == asdict(_SUBJECTS)


async def test_readiness_ai_failure_records_failed_and_never_falls_back() -> None:
    """No fallback by decision: the score, band and recommendations come only
    from the model, and no code sums the thirteen answers. The lead survives
    on the step-1 row; the report does not."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio, ai_raises=True, fallback=None)

    await service.complete(_run("readiness"))

    assert tool_runs.calls == ["finish:failed"]
    assert attio.writes == 0
    assert tool_runs.finished[0][0] == "failed"


async def test_valuation_ai_failure_uses_the_fallback_and_still_writes_attio() -> None:
    """The visitor still gets a real valuation — the model only picks the
    comparables that set the multiples."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio, ai_raises=True, fallback={"comps": []})

    await service.complete(_run("valuation"))

    assert tool_runs.calls == ["set_stage:ai", "set_stage:attio", "finish:succeeded"]
    assert tool_runs.stages[0] == ("ai", {"comps": []})
    assert attio.writes == 1


async def test_resume_reuses_stored_ai_output_and_never_pays_twice() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, ai_calls = _service(tool_runs, attio)

    await service.complete(_run(payload={"stage": "ai", "ai": {"pros": ["stored"]}}))

    assert ai_calls == []
    assert tool_runs.calls == ["set_stage:attio", "finish:succeeded"]


async def test_resume_after_a_landed_attio_write_does_not_write_twice() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio)

    await service.complete(
        _run(payload={"stage": "attio", "ai": {"pros": ["x"]}, "attio": asdict(_SUBJECTS)})
    )

    assert attio.writes == 0
    assert tool_runs.calls == ["finish:succeeded"]


async def test_attio_failure_marks_the_run_failed_without_raising() -> None:
    """`complete` never raises: the lead is already recorded, so a failure is
    the sweeper's problem, not the caller's."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio(fail=True)
    service, _ = _service(tool_runs, attio)

    await service.complete(_run())

    assert tool_runs.calls == ["set_stage:ai", "finish:failed"]
    assert "attio down" in (tool_runs.finished[0][1] or "")


@pytest.mark.parametrize("tool", ["valuation", "readiness", "benchmark", "buyer_network"])
async def test_complete_never_raises_for_any_tool(tool: Tool) -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio(fail=True)
    service, _ = _service(tool_runs, attio, ai_raises=True, fallback=None)
    await service.complete(_run(tool))
