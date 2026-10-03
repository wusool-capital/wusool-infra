"""Two simultaneous approvals of one match must create exactly one deal.

Uses committed rows and its own sessions (the shared `db_session` fixture
rides one connection, which cannot exercise a row lock), and cleans up after.
"""

import asyncio
import uuid
from types import SimpleNamespace

import pytest
from sqlalchemy import text

from app.modules.matching_engine.application.approvals import (
    ApprovalsMixin,
    InvalidTransitionError,
)
from app.modules.matching_engine.domain.matching.deals import ExistingDeal
from app.modules.matching_engine.persistence.database import get_sessionmaker
from app.modules.matching_engine.persistence.unit_of_work import SqlAlchemyMatchingUnitOfWork


class _CountingGateway:
    def __init__(self) -> None:
        self.created = 0

    async def find_pair_deals(self, *, buyer_attio_id: str, seller_attio_id: str) -> list:
        return []

    async def create_qualified(self, draft) -> ExistingDeal:
        self.created += 1
        # Long enough for the second approval to reach the row lock.
        await asyncio.sleep(0.3)
        return ExistingDeal(f"deal-{uuid.uuid4().hex[:8]}", draft.name, "Qualified", None)

    async def promote_to_qualified(self, deal_attio_id: str) -> None:
        raise AssertionError("not used")


async def test_double_approval_creates_one_deal() -> None:
    sessionmaker = get_sessionmaker()
    tag = uuid.uuid4().hex[:8]
    buyer_org, seller_org = f"wp5-buyer-{tag}", f"wp5-seller-{tag}"
    buyer_role_id, run_id, match_id = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
    try:
        async with sessionmaker() as s:
            await s.execute(text("select 1"))
    except Exception as exc:
        pytest.skip(f"database not reachable: {exc}")

    async def cleanup() -> None:
        async with sessionmaker() as s:
            await s.execute(text("delete from match_results where run_id = :r"), {"r": run_id})
            await s.execute(text("delete from deals where name like :n"), {"n": f"%{tag}%"})
            await s.execute(text("delete from buyer_roles where id = :i"), {"i": buyer_role_id})
            await s.execute(
                text("delete from organizations where attio_id in (:b, :s)"),
                {"b": buyer_org, "s": seller_org},
            )
            await s.commit()

    async with sessionmaker() as s:
        for org in (buyer_org, seller_org):
            await s.execute(
                text("insert into organizations(attio_id, name) values (:i, :n)"),
                {"i": org, "n": f"{org}-{tag}"},
            )
        await s.execute(
            text("insert into buyer_roles(id, org_attio_id) values (:i, :o)"),
            {"i": buyer_role_id, "o": buyer_org},
        )
        await s.execute(
            text(
                "insert into match_results(id, run_id, buyer_attio_id, buyer_role_id, rank, "
                "seller_attio_id, status) values (:i, :r, :b, :br, 1, :s, 'PENDING_REVIEW')"
            ),
            {"i": match_id, "r": run_id, "b": buyer_org, "br": buyer_role_id, "s": seller_org},
        )
        await s.commit()

    try:
        gateway = _CountingGateway()
        service = ApprovalsMixin(
            lambda: SqlAlchemyMatchingUnitOfWork(sessionmaker),
            buyer_repository=SimpleNamespace(),
            extraction_service=SimpleNamespace(),
            reasoning_service=SimpleNamespace(),
            candidate_retriever=SimpleNamespace(),
            scoring_engine=SimpleNamespace(),
            top_n=0,
            deal_gateway=gateway,
        )

        results = await asyncio.gather(
            service.approve_match(match_id, "U_ONE"),
            service.approve_match(match_id, "U_TWO"),
            return_exceptions=True,
        )

        assert gateway.created == 1
        assert sum(1 for r in results if isinstance(r, InvalidTransitionError)) == 1
        assert sum(1 for r in results if getattr(r, "status", None) == "APPROVED") == 1
        async with sessionmaker() as s:
            row = (
                await s.execute(
                    text("select status, deal_attio_id from match_results where id = :i"),
                    {"i": match_id},
                )
            ).one()
        assert row.status == "APPROVED"
        assert row.deal_attio_id is not None
    finally:
        await cleanup()
