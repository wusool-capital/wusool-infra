"""The write contract end to end, against a real Postgres.

Fakes exist only at the network seams. Everything else — dedup, the ledger,
the domain scoring, the resume logic — is the real code path, which is what
distinguishes these from the unit tests: they exercise the ordering, the
foreign keys and the sweeper against real SQL rather than a fake port.

`test_readiness_ai_failure_is_never_resumed_by_the_sweeper` is here because
this shape of test caught a real bug. `payload.stage` records the last step
that **completed**, so a run that failed at the AI step has no stage at all.
The retry ceilings originally read `stage` as "where it failed", which
inverted two classes: an Attio failure (free to retry) got the AI ceiling,
and a readiness AI failure fell through to the default of 6 — so the one
case that must never be retried was resumed and re-billed Bedrock. The unit
test missed it because it set `stage="ai"` by hand, a state the real flow
never produces for that failure.
"""

import uuid

import pytest
from sqlalchemy import select

from app.models.tool_run import ToolRun
from app.modules.lead_magnets.application.shared.submit import SubmissionService
from app.modules.lead_magnets.application.shared.sweeper import sweep_once
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.lead_magnets.persistence.tool_runs_repository import ToolRunsRepository
from app.modules.utilities.domain.json_types import JsonObject
from app.modules.utilities.domain.provider_errors import BedrockInvocationError


class _FakeAttio:
    """Counts per company, not globally.

    `sweep_once` is table-wide by design, so a sweep in one test can
    legitimately pick up a stale row left committed by something else. A
    global counter would make every assertion here depend on what else is in
    the database; counting per company keeps "not re-billed" a statement
    about *this* run.
    """

    def __init__(self, *, fail_times: int = 0) -> None:
        self.calls_for: dict[str, int] = {}
        self._fail_times = fail_times

    def calls(self, company: str) -> int:
        return self.calls_for.get(company, 0)

    async def write(self, *, tool, payload, ai) -> SubjectRefs:
        company = payload.get("company_name", "Acme")
        self.calls_for[company] = self.calls_for.get(company, 0) + 1
        if self.calls_for[company] <= self._fail_times:
            raise RuntimeError("Attio 503")
        return SubjectRefs(
            org_attio_id=f"org-{uuid.uuid4()}",
            org_name=payload.get("company_name", "Acme"),
            person_attio_id=f"person-{uuid.uuid4()}",
            person_name=payload.get("contact_name", "Dana"),
            seller_role_entry_id=f"entry-{uuid.uuid4()}",
        )


class _Spy:
    """Counts model calls per company, so a test can assert that output
    already paid for is never re-earned for the run under test."""

    def __init__(self, *, raises: bool = False, output: JsonObject | None = None) -> None:
        self.calls_for: dict[str, int] = {}
        self._raises = raises
        self._output = output or {"comps": [{"co": "Americana", "tk": "AMR"}]}

    def calls(self, company: str) -> int:
        return self.calls_for.get(company, 0)

    async def run(self, tool: str, payload: JsonObject) -> JsonObject:
        company = payload.get("company_name", "Acme")
        self.calls_for[company] = self.calls_for.get(company, 0) + 1
        if self._raises:
            raise BedrockInvocationError("ThrottlingException")
        return self._output


def _service(session, attio, ai, *, fallback=None) -> SubmissionService:
    return SubmissionService(
        tool_runs=ToolRunsRepository(session),
        attio=attio,
        run_ai=ai.run,
        fallback=fallback if fallback is not None else (lambda t, p: {"comps": []}),
    )


_CO = "Acme Restaurant Group LLC"


async def _row(session, run_id) -> ToolRun:
    return (await session.execute(select(ToolRun).where(ToolRun.id == run_id))).scalar_one()


async def test_benchmark_submission_completes_and_satisfies_every_fk(db_session) -> None:
    """The happy path, including the ordering trap: the org and person exist
    only in Attio when `finish` runs, so the FKs are only satisfiable
    because `finish` seeds them."""
    repo = ToolRunsRepository(db_session)
    attio, ai = _FakeAttio(), _Spy(output={"score": 55})
    service = _service(db_session, attio, ai)

    run_id, is_new = await service.record(
        tool="benchmark",
        payload={"company_name": _CO, "contact_name": "Dana"},
        email="Dana@AcmeGroup.ae",
        domain="https://www.acmegroup.ae/about",
        submission_id=str(uuid.uuid4()),
    )
    assert is_new
    # Step 1 only — the visitor's response goes out here, before any provider.
    before = await _row(db_session, run_id)
    assert before.status == "running"
    assert before.organization_attio_id is None
    assert attio.calls(_CO) == 0 and ai.calls(_CO) == 0

    await service.complete(await repo.get(run_id))

    after = await _row(db_session, run_id)
    assert after.status == "succeeded"
    assert after.organization_attio_id is not None
    assert after.person_attio_id is not None
    assert after.payload["stage"] == "attio"
    assert after.finished_at is not None
    assert attio.calls(_CO) == 1

    # The idempotency key is built from normalised values, not raw form input.
    assert after.idempotency_key == (
        f"benchmark|dana@acmegroup.ae|acmegroup.ae|{after.idempotency_key.rsplit('|', 1)[1]}"
    )


async def test_readiness_ai_failure_keeps_the_lead(db_session) -> None:
    """The live defect this module exists to close: the readiness tool has no
    fallback, so a failed model call means no report — but the submission and
    its raw answers must still be on disk."""
    repo = ToolRunsRepository(db_session)
    attio, ai = _FakeAttio(), _Spy(raises=True)
    service = _service(db_session, attio, ai, fallback=lambda t, p: None)

    run_id, _ = await service.record(
        tool="readiness",
        payload={
            "company_name": "Beta Trading FZ-LLC",
            "answers": {"q2": 0, "q14": "GCC contracts"},
        },
        email="sam@betatrading.ae",
        domain="betatrading.ae",
        submission_id=str(uuid.uuid4()),
    )
    await service.complete(await repo.get(run_id))

    row = await _row(db_session, run_id)
    assert row.status == "failed"
    assert row.payload["company_name"] == "Beta Trading FZ-LLC"
    assert row.payload["answers"]["q2"] == 0
    assert row.payload["answers"]["q14"] == "GCC contracts"
    # No report to write, so Attio is untouched; and the model is not retried.
    assert attio.calls("Beta Trading FZ-LLC") == 0
    assert ai.calls("Beta Trading FZ-LLC") == 1


async def test_attio_outage_is_drained_by_the_sweeper_without_re_billing(db_session) -> None:
    repo = ToolRunsRepository(db_session)
    attio, ai = _FakeAttio(fail_times=1), _Spy()
    service = _service(db_session, attio, ai)

    run_id, _ = await service.record(
        tool="valuation",
        payload={"company_name": "Gamma Fitout"},
        email="g@gamma.ae",
        domain="gamma.ae",
        submission_id=str(uuid.uuid4()),
    )
    await service.complete(await repo.get(run_id))

    failed = await _row(db_session, run_id)
    assert failed.status == "failed"
    # The AI stage completed, so its output is stored and already paid for.
    assert failed.payload["stage"] == "ai"
    assert failed.payload["ai"]["comps"][0]["tk"] == "AMR"

    # Not the returned count: `sweep_once` sweeps the whole table, so any
    # other stale row in the database would make a count assertion flaky.
    # What matters is what happened to *this* run.
    await sweep_once(repo, service, stale_after_s=0)

    drained = await _row(db_session, run_id)
    assert drained.status == "succeeded"
    assert drained.attempt_count == 2
    assert attio.calls("Gamma Fitout") == 2
    # The one property that makes a resume safe to run on a timer.
    assert ai.calls("Gamma Fitout") == 1


async def test_readiness_ai_failure_is_never_resumed_by_the_sweeper(db_session) -> None:
    """Regression net for the inverted-ceiling bug. Readiness has no
    fallback, so a resume would re-call Bedrock for a report the visitor has
    already been shown an error for. The run must go terminal instead.
    """
    repo = ToolRunsRepository(db_session)
    attio, failing = _FakeAttio(), _Spy(raises=True)
    service = _service(db_session, attio, failing, fallback=lambda t, p: None)

    run_id, _ = await service.record(
        tool="readiness",
        payload={"company_name": "Delta Co"},
        email="d@delta.ae",
        domain="delta.ae",
        submission_id=str(uuid.uuid4()),
    )
    await service.complete(await repo.get(run_id))
    assert (await _row(db_session, run_id)).payload.get("stage") is None

    # A sweeper whose model call would succeed must still not touch it.
    working = _Spy()
    await sweep_once(
        repo, _service(db_session, attio, working, fallback=lambda t, p: None), stale_after_s=0
    )

    row = await _row(db_session, run_id)
    assert row.status == "abandoned", "past its ceiling it goes terminal, for a human"
    assert row.attempt_count == 1, "never re-attempted"
    # No AI output was ever stored for it, which is what proves the resume
    # never ran — more robust than counting the spy, since the sweep is
    # table-wide and may legitimately touch other rows.
    assert "ai" not in row.payload
    assert working.calls("Delta Co") == 0, "Bedrock must not be re-billed"
    assert attio.calls("Delta Co") == 0


async def test_a_valuation_ai_failure_does_resume_from_its_fallback(db_session) -> None:
    """The other side of the same rule: valuation has a deterministic
    fallback, so one resume is free and the visitor still gets a result."""
    repo = ToolRunsRepository(db_session)
    attio, failing = _FakeAttio(), _Spy(raises=True)
    service = _service(db_session, attio, failing, fallback=lambda t, p: None)

    run_id, _ = await service.record(
        tool="valuation",
        payload={"company_name": "Epsilon Ltd"},
        email="e@epsilon.ae",
        domain="epsilon.ae",
        submission_id=str(uuid.uuid4()),
    )
    await service.complete(await repo.get(run_id))
    assert (await _row(db_session, run_id)).status == "failed"

    # The returned count is not asserted: `sweep_once` is table-wide, so any
    # other stale row would change it. The run under test is what matters.
    await sweep_once(
        repo,
        _service(db_session, attio, _Spy(), fallback=lambda t, p: {"comps": []}),
        stale_after_s=0,
    )
    resumed_row = await _row(db_session, run_id)
    assert resumed_row.status == "succeeded"
    assert resumed_row.attempt_count == 2


@pytest.mark.parametrize("clicks", [2, 3])
async def test_double_click_creates_one_row(db_session, clicks: int) -> None:
    attio, ai = _FakeAttio(), _Spy()
    service = _service(db_session, attio, ai)
    submission_id = str(uuid.uuid4())

    seen = [
        await service.record(
            tool="benchmark",
            payload={"n": n},
            email="d@acme.ae",
            domain="acme.ae",
            submission_id=submission_id,
        )
        for n in range(clicks)
    ]
    ids = {run_id for run_id, _ in seen}
    assert len(ids) == 1
    assert [is_new for _, is_new in seen] == [True] + [False] * (clicks - 1)
    # The first payload wins; a replay never overwrites it.
    assert (await _row(db_session, ids.pop())).payload["n"] == 0
