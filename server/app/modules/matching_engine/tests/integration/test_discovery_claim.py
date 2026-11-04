"""One search outside the CRM per run, enforced on the run row: two racing
claims get exactly one winner, a recorded outcome blocks a repeat, a release
allows one, and a claim abandoned past the stale window can be retaken.

Uses committed rows and its own sessions, like test_concurrent_approval.
"""

import asyncio
import uuid
from datetime import timedelta

import pytest
from sqlalchemy import text

from app.modules.matching_engine.application.matching.use_cases import MatchingMixin
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.persistence.unit_of_work import SqlAlchemyMatchingUnitOfWork


def _service(sessionmaker) -> MatchingMixin:
    return MatchingMixin(
        lambda: SqlAlchemyMatchingUnitOfWork(sessionmaker),
        buyer_repository=None,
        extraction_service=None,
        reasoning_service=None,
        candidate_retriever=None,
        scoring_engine=None,
        top_n=0,
        deal_gateway=None,
    )


async def test_discovery_claim_lifecycle() -> None:
    sessionmaker = get_sessionmaker()
    try:
        async with sessionmaker() as s:
            await s.execute(text("select 1"))
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    tag = uuid.uuid4().hex[:8]
    buyer_org, buyer_role_id, run_id = f"claim-buyer-{tag}", uuid.uuid4(), uuid.uuid4()
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
                "status) values (:i, :r, :b, :br, null, 'GENERATED')"
            ),
            {"i": uuid.uuid4(), "r": run_id, "b": buyer_org, "br": buyer_role_id},
        )
        await s.commit()

    service = _service(sessionmaker)
    window = timedelta(minutes=15)
    try:
        first, second = await asyncio.gather(
            service.claim_discovery(run_id, stale_after=window),
            service.claim_discovery(run_id, stale_after=window),
        )
        assert sorted([first, second]) == [False, True]

        await service.finish_discovery(
            run_id, outcome="done", message="Found 1 new seller(s)", notes=("a note",)
        )
        run = (await service.get_match_analysis(run_id)).run
        assert run.discovery is not None
        assert run.discovery.outcome == "done"
        assert run.discovery.notes == ("a note",)
        # A finished search is never retaken, however old.
        assert not await service.claim_discovery(run_id, stale_after=timedelta(0))

        await service.finish_discovery(run_id, outcome=None)
        assert (await service.get_match_analysis(run_id)).run.discovery is None
        assert await service.claim_discovery(run_id, stale_after=window)

        # Claimed but never finished: blocked inside the window, retaken after it.
        assert not await service.claim_discovery(run_id, stale_after=window)
        await asyncio.sleep(0.01)
        assert await service.claim_discovery(run_id, stale_after=timedelta(0))
    finally:
        async with sessionmaker() as s:
            await s.execute(text("delete from match_results where run_id = :r"), {"r": run_id})
            await s.execute(text("delete from buyer_roles where id = :i"), {"i": buyer_role_id})
            await s.execute(text("delete from organizations where attio_id = :o"), {"o": buyer_org})
            await s.commit()
