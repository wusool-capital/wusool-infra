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


class _FakeMailer:
    """Email is not under test here — `email_from=""` makes both email
    stages permanent no-ops, so `send` should never actually be called."""

    async def send(self, **kwargs) -> None:
        raise AssertionError("email not configured for these tests; should never be called")


def _service(session, attio, ai, *, fallback=None) -> SubmissionService:
    return SubmissionService(
        tool_runs=ToolRunsRepository(session),
        attio=attio,
        run_ai=ai.run,
        fallback=fallback if fallback is not None else (lambda t, p: {"comps": []}),
        mailer=_FakeMailer(),
        email_from="",
        email_to=[],
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

    run_id = await service.record(
        tool="benchmark",
        payload={"company_name": _CO, "contact_name": "Dana"},
        email="Dana@AcmeGroup.ae",
        domain="https://www.acmegroup.ae/about",
    )
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
    # "email_internal", not "attio" — the last-completed stage marker moves
    # past both email stages once they exist, even with email unconfigured
    # (email_from="" in `_service` above, so both are permanent no-ops).
    assert after.payload["stage"] == "email_internal"
    assert after.finished_at is not None
    assert attio.calls(_CO) == 1

    # The idempotency key is built from normalised values, not raw form
    # input, and carries no tool.
    assert after.idempotency_key == "dana@acmegroup.ae|acmegroup.ae"


async def test_readiness_ai_failure_keeps_the_lead(db_session) -> None:
    """The live defect this module exists to close: the readiness tool has no
    fallback, so a failed model call means no report — but the submission and
    its raw answers must still be on disk."""
    repo = ToolRunsRepository(db_session)
    attio, ai = _FakeAttio(), _Spy(raises=True)
    service = _service(db_session, attio, ai, fallback=lambda t, p: None)

    run_id = await service.record(
        tool="readiness",
        payload={
            "company_name": "Beta Trading FZ-LLC",
            "answers": {"q2": 0, "q14": "GCC contracts"},
        },
        email="sam@betatrading.ae",
        domain="betatrading.ae",
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

    run_id = await service.record(
        tool="valuation",
        payload={"company_name": "Gamma Fitout"},
        email="g@gamma.ae",
        domain="gamma.ae",
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

    run_id = await service.record(
        tool="readiness",
        payload={"company_name": "Delta Co"},
        email="d@delta.ae",
        domain="delta.ae",
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

    run_id = await service.record(
        tool="valuation",
        payload={"company_name": "Epsilon Ltd"},
        email="e@epsilon.ae",
        domain="epsilon.ae",
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
async def test_repeat_submissions_each_get_their_own_row_and_activity(
    db_session, clicks: int
) -> None:
    """No blocking, no overwrite: every genuinely new submission — its own
    distinct `submission_id` — gets its own permanent `tool_runs` row, and
    once completed, its own `activities` row. Nothing is ever merged away."""
    from app.models.activity import Activity

    attio, ai = _FakeAttio(), _Spy()
    service = _service(db_session, attio, ai)

    run_ids = []
    for n in range(clicks):
        run_id = await service.record(
            tool="benchmark",
            payload={"n": n, "submission_id": f"s{n}", "company_name": _CO},
            email="d@acme.ae",
            domain="acme.ae",
        )
        run_ids.append(run_id)
        await service.complete(await ToolRunsRepository(db_session).get(run_id))

    assert len(set(run_ids)) == clicks, "every submission keeps its own row"
    for n, run_id in enumerate(run_ids):
        assert (await _row(db_session, run_id)).payload["n"] == n

    activities = (
        (await db_session.execute(select(Activity).where(Activity.tool_run_id.in_(run_ids))))
        .scalars()
        .all()
    )
    assert len(activities) == clicks


async def test_exact_retry_of_the_same_submission_does_not_write_attio_twice(db_session) -> None:
    """The regression this module must not reintroduce: a plain network
    retry of the identical POST (same `submission_id`) reuses the row
    `start()` already returned, so completing it twice must not double the
    Attio write or the activity log — only a genuinely new `submission_id`
    should ever do that (covered above)."""
    from app.models.activity import Activity

    repo = ToolRunsRepository(db_session)
    attio, ai = _FakeAttio(), _Spy()
    service = _service(db_session, attio, ai)

    payload = {"submission_id": "s-retry-1", "company_name": _CO}
    first_run_id = await service.record(
        tool="benchmark", payload=payload, email="d@acme.ae", domain="acme.ae"
    )
    second_run_id = await service.record(
        tool="benchmark", payload=payload, email="d@acme.ae", domain="acme.ae"
    )
    assert first_run_id == second_run_id, "an exact retry reuses the same row"

    await service.complete(await repo.get(first_run_id))
    await service.complete(await repo.get(second_run_id))

    assert attio.calls(_CO) == 1, "the retry must not repeat the Attio write"
    activities = (
        (await db_session.execute(select(Activity).where(Activity.tool_run_id == first_run_id)))
        .scalars()
        .all()
    )
    assert len(activities) == 1, "the retry must not double the activity log"


async def test_readiness_repeat_submission_is_not_rejected_and_calls_bedrock_again(
    db_session, monkeypatch
) -> None:
    """A genuinely different visit (different `submission_id`) from the same
    person must not be rejected, and gets its own row and its own Bedrock
    call — no dedup at the client-identity level any more."""
    from fastapi import BackgroundTasks

    from app.modules.lead_magnets.api.readiness import endpoints as readiness_endpoints
    from app.modules.lead_magnets.api.schemas import ReadinessAnswersIn, ReadinessRequest
    from app.modules.lead_magnets.domain.shared.schemas import (
        ReadinessDimension,
        ReadinessRecommendation,
        ReadinessResult,
    )

    fake_result = ReadinessResult(
        overallScore=50.0,
        scoreBand="Early Stage",
        summaryParagraph="x",
        dimensions=[ReadinessDimension(name=f"Dim {i}", score=50, insight="x") for i in range(5)],
        recommendations=[ReadinessRecommendation(title=f"Rec {i}", detail="y") for i in range(3)],
    )
    calls = {"n": 0}

    class _FakeLlm:
        async def score_readiness(self, prompt):
            calls["n"] += 1
            return fake_result

    monkeypatch.setattr(readiness_endpoints, "build_llm", lambda: _FakeLlm())

    def request(submission_id: str) -> ReadinessRequest:
        return ReadinessRequest(
            submission_id=submission_id,
            name="Sam",
            company="Eta Trading",
            email="sam@etatrading.ae",
            sector="Contracting",
            domain="etatrading.ae",
            answers=ReadinessAnswersIn(q1=2),
        )

    first = await readiness_endpoints.readiness_score(request("s-1"), db_session, BackgroundTasks())
    second = await readiness_endpoints.readiness_score(
        request("s-2"), db_session, BackgroundTasks()
    )

    assert first.run_id != second.run_id
    assert calls["n"] == 2, "a genuinely new visit always pays for its own Bedrock call"


async def test_readiness_exact_retry_reuses_the_stored_score_without_a_second_bedrock_call(
    db_session, monkeypatch
) -> None:
    """A retried POST of the exact same request (same `submission_id`) must
    reuse the already-stored score instead of paying for Bedrock twice, and
    must return the identical result both times — the one case this module
    still collapses onto a single row, since it's the same click landing
    twice, not a new visit."""
    from fastapi import BackgroundTasks

    from app.modules.lead_magnets.api.readiness import endpoints as readiness_endpoints
    from app.modules.lead_magnets.api.schemas import ReadinessAnswersIn, ReadinessRequest
    from app.modules.lead_magnets.domain.shared.schemas import (
        ReadinessDimension,
        ReadinessRecommendation,
        ReadinessResult,
    )

    fake_result = ReadinessResult(
        overallScore=72.5,
        scoreBand="Getting There",
        summaryParagraph="A solid start.",
        dimensions=[ReadinessDimension(name=f"Dim {i}", score=70, insight="x") for i in range(5)],
        recommendations=[ReadinessRecommendation(title=f"Rec {i}", detail="y") for i in range(3)],
    )
    calls = {"n": 0}

    class _FakeLlm:
        async def score_readiness(self, prompt):
            calls["n"] += 1
            return fake_result

    monkeypatch.setattr(readiness_endpoints, "build_llm", lambda: _FakeLlm())

    request = ReadinessRequest(
        submission_id="s-replay-1",
        name="Sam",
        company="Zeta Trading",
        email="sam@zetatrading.ae",
        sector="Contracting",
        domain="zetatrading.ae",
        answers=ReadinessAnswersIn(q1=2),
    )

    first = await readiness_endpoints.readiness_score(request, db_session, BackgroundTasks())
    second = await readiness_endpoints.readiness_score(request, db_session, BackgroundTasks())

    assert calls["n"] == 1, "Bedrock must not be re-billed for the exact same request"
    assert first.run_id == second.run_id
    assert second.overallScore == fake_result.overallScore
    assert second.summaryParagraph == fake_result.summaryParagraph


async def test_real_attio_writers_seed_the_person_stub_and_fk(db_session) -> None:
    """Wires the real `_RoleAttioWriter` (`AttioRoleWriter` +
    `AttioPersonWriter`) over a fake `AttioClientProtocol` — the one seam
    `_FakeAttio` above skips entirely — and confirms the person half of the
    ordering trap resolves the same way the org half already does: the
    Postgres `person` stub, `tool_runs.person_attio_id`, and an `activities`
    row all land from a single Attio write. Also pins that the `deal` write
    rides the same pass and survives the `asdict` -> JSONB -> `SubjectRefs`
    round trip."""
    from app.models.activity import Activity
    from app.models.person import Person
    from app.modules.lead_magnets.bootstrap import _RoleAttioWriter
    from app.modules.lead_magnets.providers.attio.deal_writer import AttioDealWriter
    from app.modules.lead_magnets.providers.attio.person_writer import AttioPersonWriter
    from app.modules.lead_magnets.providers.attio.role_writer import AttioRoleWriter
    from app.modules.organizations import OrganizationRepository

    class _FakeAttioClient:
        def __init__(self) -> None:
            self.deals_created = 0

        async def post(self, path: str, json_body: dict) -> dict:
            if path == "/objects/deal/records/query":
                return {"data": []}
            if path == "/objects/deal/records":
                self.deals_created += 1
                return {"data": {"id": {"record_id": "deal-e2e-1"}}}
            if path == "/objects/organizations/records":
                return {"data": {"id": {"record_id": "org-e2e-1"}}}
            if path == "/lists/seller_role/entries/query":
                return {"data": []}
            if path == "/lists/seller_role/entries":
                return {"data": {"id": {"entry_id": "entry-e2e-1"}}}
            if path == "/objects/person/records/query":
                return {"data": []}
            if path == "/objects/person/records":
                return {"data": {"id": {"record_id": "person-e2e-1"}}}
            raise AssertionError(f"unexpected post {path}")

        async def get(self, path: str) -> dict:
            raise AssertionError(f"unexpected get {path}")

        async def patch(self, path: str, json_body: dict) -> dict:
            raise AssertionError(f"unexpected patch {path}")

    client = _FakeAttioClient()
    role_attio_writer = _RoleAttioWriter(
        AttioRoleWriter(client, is_test=True),
        OrganizationRepository(db_session),
        AttioPersonWriter(client, is_test=True),
        AttioDealWriter(client, is_test=True, owner_id="owner-1", fallback_owner_id="owner-2"),
    )
    repo = ToolRunsRepository(db_session)
    service = SubmissionService(
        tool_runs=repo,
        attio=role_attio_writer,
        run_ai=_Spy(output={"entry_values": {}}).run,
        fallback=lambda t, p: {"entry_values": {}},
        mailer=_FakeMailer(),
        email_from="",
        email_to=[],
    )

    run_id = await service.record(
        tool="valuation",
        payload={"company": "Zeta Fitout LLC", "email": "z@zetafitout.ae"},
        email="z@zetafitout.ae",
        domain="zetafitout.ae",
    )

    await service.complete(await repo.get(run_id))

    row = await _row(db_session, run_id)
    assert row.status == "succeeded"
    assert row.organization_attio_id == "org-e2e-1"
    assert row.person_attio_id == "person-e2e-1"

    activity = (
        await db_session.execute(select(Activity).where(Activity.tool_run_id == run_id))
    ).scalar_one()
    assert activity.subject_type == "Organization"
    assert activity.subject_attio_id == "org-e2e-1"

    person = (
        await db_session.execute(select(Person).where(Person.attio_id == "person-e2e-1"))
    ).scalar_one()
    assert person.name

    assert row.payload["attio"]["deal_attio_id"] == "deal-e2e-1"

    # A resume reads `payload.attio` back and must not write Attio again —
    # without that, a crash between `set_stage` and `finish` would drop a
    # second card into the pipeline.
    await service.complete(await repo.get(run_id))
    assert client.deals_created == 1


async def test_get_started_runs_its_real_pipeline_end_to_end(db_session) -> None:
    """The only tool whose pipeline calls no model at all, so this runs the
    *real* `Pipelines.run` rather than a `_Spy` — the entry values reaching
    Attio are the genuine `get_started_values` output, including the first
    pipeline write this codebase makes to `sell_timeline`.

    Uses `_service()`, not a hand-built `SubmissionService(...)`, so this
    test can't go stale the way it did the first time: `_service` already
    carries `mailer=_FakeMailer()`/`email_from=""`/`email_to=[]`, so both
    email stages are permanent no-ops here — the point of this test is the
    pipeline output, not the email step (see the tests further down for
    that). `email_from=""` is also why the terminal stage is
    `"email_internal"`, not `"attio"`: both email stages still run and set
    their own stage even when skipped, they just never call the mailer.
    """
    from app.modules.lead_magnets.application.shared.pipelines import Pipelines

    repo = ToolRunsRepository(db_session)
    attio = _FakeAttio()
    pipelines = Pipelines(llm=None)  # type: ignore[arg-type]  # no model is reached
    service = _service(db_session, attio, pipelines, fallback=pipelines.fallback)

    run_id, outcome = await service.record(
        tool="get_started",
        payload={
            "company": _CO,
            "company_name": _CO,  # what `_FakeAttio` counts per company
            "name": "Dana",
            "email": "Dana@AcmeGroup.ae",
            "geography": "UAE",
            "sector": "F&B",
            "revenue": 3_268_209,
            "ebitda": 653_641,
            "years_active": 8,
            "sell_timeline": "Within 6 Months",
            "consent": True,
        },
        email="Dana@AcmeGroup.ae",
        domain="https://www.acmegroup.ae/about",
    )
    assert outcome == "new"

    await service.complete(await repo.get(run_id))

    after = await _row(db_session, run_id)
    assert after.status == "succeeded"
    assert after.payload["stage"] == "email_internal"
    assert after.idempotency_key == "get_started|dana@acmegroup.ae|acmegroup.ae"
    assert attio.calls(_CO) == 1

    entry_values = after.payload["ai"]["entry_values"]
    assert entry_values["sell_timeline"] == "Within 6 Months"
    assert entry_values["years_active"] == 8
    assert entry_values["est_revenue"] == {"currency_value": 3_268_209.0}
    assert entry_values["est_ebitda"] == {"currency_value": 653_641.0}
    assert entry_values["data_consent"] is True
