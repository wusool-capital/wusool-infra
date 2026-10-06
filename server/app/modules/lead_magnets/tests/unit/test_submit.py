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
        self.finished_subjects: list[SubjectRefs] = []

    async def start(self, *, tool, payload, idempotency_key):
        self.calls.append("start")
        self.started.append((tool, idempotency_key))
        return uuid4()

    async def set_stage(self, run_id, *, stage, output=None):
        self.calls.append(f"set_stage:{stage}")
        self.stages.append((stage, output))

    async def finish(self, run_id, status, *, subjects=_NO_SUBJECTS, error=None):
        self.calls.append(f"finish:{status}")
        self.finished.append((status, error))
        self.finished_subjects.append(subjects)

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


class _FakeMailer:
    """Records every send, in order. `fail_on` names which recipient group
    ("confirmation"/"internal", by the `to` list's shape) should raise —
    the visitor gets one address, the internal team a fixed fake list."""

    def __init__(self, *, fail_on: str | None = None) -> None:
        self.sent: list[tuple[list[str], str]] = []
        self._fail_on = fail_on

    async def send(self, *, to, from_addr, subject, body, is_html=False):
        kind = "internal" if to == _INTERNAL_TO else "confirmation"
        if kind == self._fail_on:
            raise RuntimeError(f"ses down ({kind})")
        self.sent.append((to, subject))


_INTERNAL_TO = ["ops@wusoolcapital.com"]


def _run(
    tool: Tool = "valuation", payload: JsonObject | None = None, *, status: str = "running"
) -> ToolRunRecord:
    return ToolRunRecord(
        id=UUID("11111111-1111-4111-8111-111111111111"),
        tool=tool,
        status=status,
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
    mailer: _FakeMailer | None = None,
    email_from: str = "tech@wusoolcapital.com",
    email_to: list[str] | None = None,
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
        SubmissionService(
            tool_runs=tool_runs,
            attio=attio,
            run_ai=run_ai,
            fallback=run_fallback,
            mailer=mailer or _FakeMailer(),
            email_from=email_from,
            email_to=email_to if email_to is not None else _INTERNAL_TO,
        ),
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
    )

    assert tool_runs.calls == ["start"]
    assert ai_calls == []
    assert attio.writes == 0
    # The key is normalised, not the raw form input, and carries no tool.
    assert tool_runs.started[0] == ("readiness", "f@acme.com|acme.com")


async def test_complete_is_a_no_op_on_an_already_succeeded_run() -> None:
    """An exact-retry's row is completed twice (once for the original
    request, once for the retry landing on the same row) — the second call
    must not redo the Attio write or log a second activity, even though
    every individual step below already reuses stored output on its own."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, ai_calls = _service(tool_runs, attio)

    await service.complete(_run(status="succeeded"))

    assert tool_runs.calls == []
    assert ai_calls == []
    assert attio.writes == 0


async def test_happy_path_order() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer()
    service, ai_calls = _service(tool_runs, attio, mailer=mailer)

    await service.complete(_run())

    assert tool_runs.calls == [
        "set_stage:ai",
        "set_stage:attio",
        "set_stage:email_confirmation",
        "set_stage:email_internal",
        "finish:succeeded",
    ]
    assert ai_calls == ["valuation"]
    assert attio.writes == 1
    # No "email" key on the default payload: the visitor confirmation has
    # nothing to send to, so only the internal notice actually goes out.
    assert [to for to, _ in mailer.sent] == [_INTERNAL_TO]


async def test_attio_stage_is_recorded_before_finish() -> None:
    """A crash between the two must leave a row that knows Attio is already
    done, or the resume writes Attio twice and duplicates the record."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio)

    await service.complete(_run())

    assert tool_runs.calls.index("set_stage:attio") < tool_runs.calls.index("finish:succeeded")
    stages = dict(tool_runs.stages)
    assert stages["attio"] == asdict(_SUBJECTS)


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

    assert tool_runs.calls == [
        "set_stage:ai",
        "set_stage:attio",
        "set_stage:email_confirmation",
        "set_stage:email_internal",
        "finish:succeeded",
    ]
    assert tool_runs.stages[0] == ("ai", {"comps": []})
    assert attio.writes == 1


async def test_resume_reuses_stored_ai_output_and_never_pays_twice() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, ai_calls = _service(tool_runs, attio)

    await service.complete(_run(payload={"stage": "ai", "ai": {"pros": ["stored"]}}))

    assert ai_calls == []
    assert tool_runs.calls == [
        "set_stage:attio",
        "set_stage:email_confirmation",
        "set_stage:email_internal",
        "finish:succeeded",
    ]


async def test_resume_after_a_landed_attio_write_does_not_write_twice() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio)

    await service.complete(
        _run(payload={"stage": "attio", "ai": {"pros": ["x"]}, "attio": asdict(_SUBJECTS)})
    )

    assert attio.writes == 0
    assert tool_runs.calls == [
        "set_stage:email_confirmation",
        "set_stage:email_internal",
        "finish:succeeded",
    ]


async def test_resume_of_a_run_stored_before_the_id_list_keeps_its_one_buyer_role() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    service, _ = _service(tool_runs, attio)
    stored = {"org_attio_id": "org-1", "buyer_role_entry_id": "entry-1"}

    await service.complete(_run(payload={"stage": "attio", "ai": {}, "attio": stored}))

    assert tool_runs.finished_subjects[-1].buyer_role_entry_ids == ("entry-1",)


async def test_attio_failure_marks_the_run_failed_without_raising() -> None:
    """`complete` never raises: the lead is already recorded, so a failure is
    the sweeper's problem, not the caller's."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio(fail=True)
    service, _ = _service(tool_runs, attio)

    await service.complete(_run())

    assert tool_runs.calls == ["set_stage:ai", "finish:failed"]
    assert "attio down" in (tool_runs.finished[0][1] or "")


@pytest.mark.parametrize(
    "tool",
    ["valuation", "readiness", "benchmark", "buyer_network", "get_started", "insights_report"],
)
async def test_complete_never_raises_for_any_tool(tool: Tool) -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio(fail=True)
    service, _ = _service(tool_runs, attio, ai_raises=True, fallback=None)
    await service.complete(_run(tool))


async def test_confirmation_email_sends_to_the_visitor_address() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer()
    service, _ = _service(tool_runs, attio, mailer=mailer)

    await service.complete(_run(payload={"email": "visitor@acme.com"}))

    assert mailer.sent[0] == (["visitor@acme.com"], "Your valuation request is in")


async def test_no_visitor_address_skips_confirmation_without_failing() -> None:
    """No `email` on the payload — nothing to retry, so the stage is marked
    done rather than left to fail forever."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer()
    service, _ = _service(tool_runs, attio, mailer=mailer)

    await service.complete(_run())

    assert ("email_confirmation", {"sent": False}) in tool_runs.stages
    assert tool_runs.calls[-1] == "finish:succeeded"


async def test_unconfigured_email_skips_both_stages_without_failing() -> None:
    """No sender configured (`LEAD_MAGNET_EMAIL_FROM` unset) — same
    permanent-skip rule, for both stages."""
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer()
    service, _ = _service(tool_runs, attio, mailer=mailer, email_from="")

    await service.complete(_run(payload={"email": "visitor@acme.com"}))

    assert mailer.sent == []
    assert dict(tool_runs.stages)["email_confirmation"] == {"sent": False}
    assert dict(tool_runs.stages)["email_internal"] == {"sent": False}
    assert tool_runs.calls[-1] == "finish:succeeded"


async def test_confirmation_failure_marks_failed_before_internal_runs() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer(fail_on="confirmation")
    service, _ = _service(tool_runs, attio, mailer=mailer)

    await service.complete(_run(payload={"email": "visitor@acme.com"}))

    assert tool_runs.calls == ["set_stage:ai", "set_stage:attio", "finish:failed"]
    assert mailer.sent == []
    # The Attio write already landed by this point — finish() must still
    # seed the org/person stub rows and log the activity, or a lead that
    # only fails on the confirmation email loses its audit trail.
    assert tool_runs.finished_subjects[-1] == _SUBJECTS


async def test_internal_failure_after_confirmation_does_not_resend_confirmation() -> None:
    """The advisor-flagged tradeoff: confirmation and internal are tracked as
    two separate stages precisely so a sweeper resume after this failure
    retries only the internal send, never the visitor's confirmation again.
    """
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer(fail_on="internal")
    service, _ = _service(tool_runs, attio, mailer=mailer)

    run = _run(payload={"email": "visitor@acme.com"})
    await service.complete(run)

    assert tool_runs.calls == [
        "set_stage:ai",
        "set_stage:attio",
        "set_stage:email_confirmation",
        "finish:failed",
    ]
    assert mailer.sent == [(["visitor@acme.com"], "Your valuation request is in")]

    # Sweeper resume: same payload, plus everything `set_stage` has recorded
    # so far, exactly like `claim_stale` would hand back.
    resumed_payload = dict(run.payload)
    for stage, output in tool_runs.stages:
        if output is not None:
            resumed_payload[stage] = output
    mailer.sent.clear()
    tool_runs.calls.clear()
    healthy_mailer_service, _ = _service(
        tool_runs, attio, mailer=_FakeMailer(), email_from="tech@wusoolcapital.com"
    )
    await healthy_mailer_service.complete(_run(payload=resumed_payload))

    assert tool_runs.calls == ["set_stage:email_internal", "finish:succeeded"]


@pytest.mark.parametrize(
    ("tool", "payload"),
    [
        (
            "get_started",
            {
                "company": "Acme",
                "sell_timeline": "Sometime, maybe",  # not one of the live 5 options
                "consent": True,
            },
        ),
        (
            "buyer_network",
            {
                "org_name": "Acme",
                "org_type": ["Private Equity"],
                "sector_focus": ["Fintech"],
                "target_geography": ["Mars"],  # not one of the live 7 options
                "email": "x@x.com",
            },
        ),
    ],
)
async def test_complete_never_raises_on_a_real_domain_vocabulary_error(
    tool: Tool, payload: JsonObject
) -> None:
    """The regression this file's fakes could not catch.

    `test_complete_never_raises_for_any_tool` above proves `complete` is
    safe when `run_ai` raises `BedrockInvocationError` — but its fake
    `run_ai` can *only* ever raise that one type, so it says nothing about
    a pipeline's own domain-vocabulary error (`UnmappedSellTimelineError`,
    `UnmappedTargetGeographyError`), which is built inside the real
    `entry_values` construction, not inside any model call. This uses the
    real `Pipelines` so the real exception is the one under test.

    Before `_ensure_ai` was broadened past `BedrockInvocationError`, this
    exact scenario propagated straight out of `complete()`, breaking its
    own "never raises" contract — and since `sweep_once` claims several
    stale rows per pass with no per-row isolation, a sweeper resume hitting
    this would have aborted the whole pass, not just this one row.

    Constructs `SubmissionService` directly rather than via `_service()`:
    that helper always builds its own fake `run_ai`/`fallback` closures, and
    this test specifically needs the real `Pipelines` so the real exception
    is the one under test. The failure happens inside `_ensure_ai`, before
    any Attio or email stage runs, so the mailer/email settings below are
    never touched either way — `_service()`'s own defaults, kept only for
    consistency with every other test in this file.
    """
    from app.modules.lead_magnets.application.shared.pipelines import Pipelines

    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    pipelines = Pipelines(llm=None)  # type: ignore[arg-type]  # never reached
    service = SubmissionService(
        tool_runs=tool_runs,
        attio=attio,
        run_ai=pipelines.run,
        fallback=pipelines.fallback,
        mailer=_FakeMailer(),
        email_from="tech@wusoolcapital.com",
        email_to=_INTERNAL_TO,
    )

    await service.complete(_run(tool, payload=payload))

    assert tool_runs.calls == ["finish:failed"]
    assert attio.writes == 0


async def test_a_report_unlock_sends_no_email_and_still_succeeds() -> None:
    tool_runs, attio = _FakeToolRuns(), _FakeAttio()
    mailer = _FakeMailer()
    service, _ = _service(tool_runs, attio, mailer=mailer)

    await service.complete(_run("insights_report", payload={"email": "dana@acme.com"}))

    assert mailer.sent == []
    assert dict(tool_runs.stages)["email_confirmation"] == {"sent": False}
    assert dict(tool_runs.stages)["email_internal"] == {"sent": False}
    assert attio.writes == 1
    assert tool_runs.calls[-1] == "finish:succeeded"
