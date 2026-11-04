"""A candidate's full research and its save are each claimed on the row: two
racing claims get one winner, a finished research isn't retaken, a failed one
is, and a retake keeps the stored LinkedIn scan.

Uses committed rows and its own sessions, like test_discovery_claim.
"""

import asyncio
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import text

from app.modules.matching_engine.domain.matching.research import (
    ResearchLinkedIn,
    ResearchRecord,
)
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.persistence.unit_of_work import SqlAlchemyMatchingUnitOfWork


async def test_research_and_save_claims() -> None:
    sessionmaker = get_sessionmaker()
    try:
        async with sessionmaker() as s:
            await s.execute(text("select 1"))
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    tag = uuid.uuid4().hex[:8]
    buyer_org, buyer_role_id = f"research-buyer-{tag}", uuid.uuid4()
    run_id, candidate_id = uuid.uuid4(), uuid.uuid4()
    async with sessionmaker() as s:
        await s.execute(
            text("insert into organizations(attio_id, name) values (:i, :n)"),
            {"i": buyer_org, "n": buyer_org},
        )
        await s.execute(
            text("insert into buyer_roles(id, org_attio_id) values (:i, :o)"),
            {"i": buyer_role_id, "o": buyer_org},
        )
        await s.execute(
            text(
                "insert into match_results(id, run_id, buyer_attio_id, buyer_role_id, rank, "
                "status) values (:i, :r, :b, :br, 1, 'APPROVED')"
            ),
            {"i": candidate_id, "r": run_id, "b": buyer_org, "br": buyer_role_id},
        )
        await s.commit()

    async def repo_call(name: str, **kwargs: datetime) -> bool:
        async with SqlAlchemyMatchingUnitOfWork(sessionmaker) as uow:
            return await getattr(uow.match_results, name)(candidate_id, **kwargs)

    async def record() -> ResearchRecord | None:
        async with SqlAlchemyMatchingUnitOfWork(sessionmaker) as uow:
            row = await uow.match_results.get_by_id(candidate_id)
            return row.research if row else None

    async def store(value: ResearchRecord) -> None:
        async with SqlAlchemyMatchingUnitOfWork(sessionmaker) as uow:
            await uow.match_results.update_research(candidate_id, value)

    now = datetime.now(UTC)
    window = {"now": now, "stale_before": now - timedelta(minutes=15)}
    try:
        first, second = await asyncio.gather(
            repo_call("claim_research", **window), repo_call("claim_research", **window)
        )
        assert sorted([first, second]) == [False, True]

        claimed = await record()
        assert claimed is not None and claimed.outcome is None
        scan = ResearchLinkedIn(outcome="completed", contacts_scanned=2)
        await store(ResearchRecord(claimed_at=claimed.claimed_at, outcome="failed", linkedin=scan))

        # A failed research is retaken, keeping its LinkedIn scan.
        assert await repo_call("claim_research", **window)
        retaken = await record()
        assert retaken is not None and retaken.outcome is None and retaken.linkedin == scan

        await store(ResearchRecord(claimed_at=retaken.claimed_at, outcome="done", linkedin=scan))
        assert not await repo_call("claim_research", now=now, stale_before=now + timedelta(1))

        saves = await asyncio.gather(
            repo_call("claim_research_save", **window),
            repo_call("claim_research_save", **window),
        )
        assert sorted(saves) == [False, True]
        # A save abandoned past the window can be retaken.
        later = now + timedelta(hours=1)
        assert await repo_call(
            "claim_research_save", now=later, stale_before=later - timedelta(minutes=15)
        )

        # Once anything is saved (or it's skipped) the review is closed for good.
        await store(
            ResearchRecord(
                claimed_at=retaken.claimed_at,
                outcome="done",
                linkedin=scan,
                saved_fields=("facebook",),
            )
        )
        assert not await repo_call("claim_research_save", now=later, stale_before=later)

        # A failed scan isn't kept on a retake, so LinkedIn is tried again.
        failed_scan = ResearchLinkedIn(outcome="failed")
        await store(
            ResearchRecord(claimed_at=retaken.claimed_at, outcome="failed", linkedin=failed_scan)
        )
        assert await repo_call("claim_research", **window)
        rescanning = await record()
        assert rescanning is not None and rescanning.linkedin is None
    finally:
        async with sessionmaker() as s:
            await s.execute(text("delete from match_results where run_id = :r"), {"r": run_id})
            await s.execute(text("delete from buyer_roles where id = :i"), {"i": buyer_role_id})
            await s.execute(text("delete from organizations where attio_id = :o"), {"o": buyer_org})
            await s.commit()
