"""The write-ahead ledger against a real Postgres.

These exist for the ordering trap above all: `tool_runs`' subject columns
are foreign keys into the Attio→Postgres mirror, and at the moment an Attio
write returns, those rows exist only in Attio. A naive `finish()` FK-violates
on every genuinely new lead — the exact case the ledger exists to survive.
"""

from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from sqlalchemy import select

from app.models.seller_role import SellerRole
from app.models.tool_run import ToolRun
from app.modules.lead_magnets.domain.tool_run import SubjectRefs
from app.modules.lead_magnets.persistence.tool_runs_repository import ToolRunsRepository


def _key() -> str:
    return f"readiness|f@acme.com|acme.com|{uuid4()}"


async def _row(session, run_id) -> ToolRun:
    return (await session.execute(select(ToolRun).where(ToolRun.id == run_id))).scalar_one()


async def test_start_records_the_submission_before_anything_else(db_session) -> None:
    repo = ToolRunsRepository(db_session)
    run_id, is_new = await repo.start(
        tool="readiness",
        payload={"email": "f@acme.com", "answers": {"q1": 3}},
        idempotency_key=_key(),
    )
    assert is_new
    row = await _row(db_session, run_id)
    assert row.status == "running"
    # The whole point: the lead is on disk with no subject resolved yet.
    assert row.organization_attio_id is None
    assert row.person_attio_id is None
    assert row.payload["answers"] == {"q1": 3}
    assert row.attempt_count == 1


async def test_replayed_idempotency_key_is_a_no_op(db_session) -> None:
    """A double-clicked button or a retried POST must not run the pipeline
    twice."""
    repo = ToolRunsRepository(db_session)
    key = _key()
    first, first_new = await repo.start(tool="readiness", payload={"n": 1}, idempotency_key=key)
    second, second_new = await repo.start(tool="readiness", payload={"n": 2}, idempotency_key=key)

    assert first == second
    assert first_new is True
    assert second_new is False
    # The original payload wins; the replay does not overwrite it.
    assert (await _row(db_session, first)).payload["n"] == 1


async def test_finish_on_a_brand_new_org_does_not_fk_violate(db_session) -> None:
    """The mirror has not run yet, so `organizations`/`person` have no row
    for these Attio ids. `finish()` seeds both stubs so the FKs hold."""
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(tool="benchmark", payload={}, idempotency_key=_key())
    org_id = f"org-{uuid4()}"
    person_id = f"person-{uuid4()}"

    await repo.finish(
        run_id,
        "succeeded",
        subjects=SubjectRefs(
            org_attio_id=org_id,
            org_name="Acme Trading LLC",
            person_attio_id=person_id,
            person_name="Dana Founder",
        ),
    )

    row = await _row(db_session, run_id)
    assert row.status == "succeeded"
    assert row.organization_attio_id == org_id
    assert row.person_attio_id == person_id
    assert row.finished_at is not None


async def test_finish_leaves_role_fk_null_until_the_mirror_lands(db_session) -> None:
    """The role row is resolved by `legacy_entry_id`, which the mirror
    creates. Until then the subquery is over no rows, so the column is NULL
    rather than an error — and `promote_role_fks` fills it in after."""
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(
        tool="valuation",
        payload={"seller_role_entry_id": "entry-xyz"},
        idempotency_key=_key(),
    )
    org_id = f"org-{uuid4()}"
    await repo.finish(
        run_id,
        "succeeded",
        subjects=SubjectRefs(
            org_attio_id=org_id, org_name="Acme", seller_role_entry_id="entry-xyz"
        ),
    )
    assert (await _row(db_session, run_id)).seller_role_id is None

    # The mirror lands the role row.
    db_session.add(SellerRole(org_attio_id=org_id, legacy_entry_id="entry-xyz"))
    await db_session.flush()

    assert await repo.promote_role_fks() >= 1
    await db_session.refresh(await _row(db_session, run_id))
    row = await _row(db_session, run_id)
    assert row.seller_role_id is not None


async def test_set_stage_merges_rather_than_replaces(db_session) -> None:
    """`payload` also holds the submission and the raw answers — a resume
    that clobbered them would lose the lead it exists to protect."""
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(
        tool="valuation", payload={"email": "f@acme.com"}, idempotency_key=_key()
    )
    await repo.set_stage(run_id, stage="ai", output={"comps": [{"tk": "AAPL"}]})

    row = await _row(db_session, run_id)
    assert row.payload["email"] == "f@acme.com"
    assert row.payload["stage"] == "ai"
    assert row.payload["ai"] == {"comps": [{"tk": "AAPL"}]}


async def test_claim_stale_only_takes_rows_past_the_cutoff(db_session) -> None:
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(tool="valuation", payload={}, idempotency_key=_key())
    await repo.set_stage(run_id, stage="attio")

    fresh_cutoff = datetime.now(UTC) - timedelta(hours=1)
    assert [r.id for r in await repo.claim_stale(cutoff=fresh_cutoff)] == []

    claimed = await repo.claim_stale(cutoff=datetime.now(UTC) + timedelta(seconds=1))
    assert run_id in [r.id for r in claimed]
    assert (await _row(db_session, run_id)).attempt_count == 2


async def test_claim_stale_cutoff_actually_advances(db_session) -> None:
    """Gating on `started_at` alone would mean the cutoff never moves and
    every sweep re-fires the same row instantly. `last_attempt_at` is what
    makes the second claim in the same instant impossible."""
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(tool="valuation", payload={}, idempotency_key=_key())
    await repo.set_stage(run_id, stage="attio")

    cutoff = datetime.now(UTC) + timedelta(seconds=1)
    assert run_id in [r.id for r in await repo.claim_stale(cutoff=cutoff)]
    # Same cutoff, immediately again: last_attempt_at is now ~now, so the
    # row must not come back until the next window.
    assert run_id not in [
        r.id for r in await repo.claim_stale(cutoff=datetime.now(UTC) - timedelta(seconds=1))
    ]


async def test_readiness_ai_failure_is_never_retried(db_session) -> None:
    """Readiness has no deterministic fallback by decision, so a resume
    would have to re-call Bedrock. Its ceiling is 1 — the original attempt
    and nothing more. The write-ahead row keeps the lead; the report is
    lost either way.

    Note the setup: an AI failure leaves **no** stage recorded, because
    `stage` marks what *completed*. Setting `stage="ai"` here would describe
    a run whose AI succeeded and whose Attio write failed — the opposite
    case, and free to retry. Getting that backwards let a real readiness
    failure be resumed and re-billed; the end-to-end simulation caught it.
    """
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(tool="readiness", payload={}, idempotency_key=_key())

    claimed = await repo.claim_stale(cutoff=datetime.now(UTC) + timedelta(seconds=1))
    assert run_id not in [r.id for r in claimed]

    abandoned = await repo.abandon_past_ceiling(cutoff=datetime.now(UTC) + timedelta(seconds=1))
    assert run_id in [r.id for r in abandoned]
    assert (await _row(db_session, run_id)).status == "abandoned"


@pytest.mark.parametrize(
    "tool,stage_completed,claims",
    [
        # 'ai' completed => the Attio write failed. The model output is
        # stored and already paid for, so retrying is free and idempotent.
        ("valuation", "ai", True),
        ("readiness", "ai", True),
        ("benchmark", "ai", True),
        # 'attio' completed => only `finish` failed. Equally free.
        ("valuation", "attio", True),
        ("readiness", "attio", True),
        # Nothing completed => the AI call itself failed. Valuation and
        # benchmark resume once, from their deterministic fallback...
        ("valuation", None, True),
        ("benchmark", None, True),
        # ...and readiness never does, because it has no fallback and a
        # resume would re-bill Bedrock for a report already shown as an error.
        ("readiness", None, False),
    ],
)
async def test_ceilings_per_failure_class(db_session, tool, stage_completed, claims) -> None:
    """`stage` is the last step that COMPLETED, not where the run failed."""
    repo = ToolRunsRepository(db_session)
    run_id, _ = await repo.start(tool=tool, payload={}, idempotency_key=_key())
    if stage_completed is not None:
        await repo.set_stage(run_id, stage=stage_completed)
    claimed = [
        r.id for r in await repo.claim_stale(cutoff=datetime.now(UTC) + timedelta(seconds=1))
    ]
    assert (run_id in claimed) is claims
