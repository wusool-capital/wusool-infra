from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.activities import ActorType, EventType, LedgerType
from app.modules.matching_engine.application.approvals import (
    ApprovalsMixin,
    InvalidTransitionError,
)
from app.modules.matching_engine.application.errors import (
    DealGatewayError,
    ExistingDealsFoundError,
    PartialWriteError,
)
from app.modules.matching_engine.domain.matching.deals import ExistingDeal


class _AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


def _candidate(**overrides):
    fields = {
        "status": "PENDING_REVIEW",
        "buyer_attio_id": "buyer-1",
        "buyer_org_name": "Buyer Co",
        "seller_attio_id": "seller-1",
        "seller_org_name": "Seller Co",
    }
    return SimpleNamespace(**{**fields, **overrides})


def _updated():
    return SimpleNamespace(
        id=str(uuid4()), run_id="r1", seller_org_name="Seller Co", seller_attio_id="seller-1",
        buyer_role_id=str(uuid4()), status="APPROVED",
    )  # fmt: skip


def _service(*, update_result=None, upsert_error=None, gateway=None, candidate=None):
    repo = SimpleNamespace(
        get_by_id_for_update=AsyncMock(return_value=candidate or _candidate()),
        update_status=AsyncMock(return_value=update_result),
    )
    deals = SimpleNamespace(upsert=AsyncMock(side_effect=upsert_error))
    activities = SimpleNamespace(record=AsyncMock())
    uow = SimpleNamespace(match_results=repo, deals=deals, activities=activities)
    # Only the approval dependencies are exercised; the rest are stand-ins.
    service = ApprovalsMixin(
        lambda: _AsyncContextManager(uow),
        buyer_repository=SimpleNamespace(),
        extraction_service=SimpleNamespace(),
        reasoning_service=SimpleNamespace(),
        candidate_retriever=SimpleNamespace(),
        scoring_engine=SimpleNamespace(),
        top_n=0,
        deal_gateway=gateway or _gateway(),
    )
    return service, repo, deals, activities


def _gateway(*, existing=None, create_error=None):
    created = ExistingDeal(
        attio_id="deal-new", name="Seller Co - Buyer Co", stage="Qualified", web_url=None
    )
    return SimpleNamespace(
        find_pair_deals=AsyncMock(return_value=existing or []),
        create_qualified=AsyncMock(side_effect=create_error, return_value=created),
        promote_to_qualified=AsyncMock(),
    )  # fmt: skip


@pytest.mark.asyncio
async def test_approve_creates_deal_then_stamps_match() -> None:
    gateway = _gateway()
    service, repo, deals, _ = _service(update_result=_updated(), gateway=gateway)

    result = await service.approve_match(uuid4(), "U_TEST")

    assert result.status == "APPROVED"
    gateway.create_qualified.assert_awaited_once()
    assert deals.upsert.await_args.args[0].attio_id == "deal-new"
    assert repo.update_status.await_args.kwargs["deal_attio_id"] == "deal-new"


@pytest.mark.asyncio
async def test_existing_deals_require_a_choice() -> None:
    existing = [ExistingDeal("deal-1", "Old", "Inbound", None)]
    gateway = _gateway(existing=existing)
    service, _, _, _ = _service(update_result=_updated(), gateway=gateway)

    with pytest.raises(ExistingDealsFoundError) as raised:
        await service.approve_match(uuid4(), "U_TEST")

    assert raised.value.deals == existing
    gateway.create_qualified.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_moves_inbound_deal_to_qualified() -> None:
    gateway = _gateway(existing=[ExistingDeal("deal-1", "Old", "Inbound", None)])
    service, repo, deals, _ = _service(update_result=_updated(), gateway=gateway)

    await service.approve_match(
        uuid4(), "U_TEST", resolution="promote_existing", existing_deal_id="deal-1"
    )

    gateway.promote_to_qualified.assert_awaited_once_with("deal-1")
    gateway.create_qualified.assert_not_awaited()
    assert deals.upsert.await_args.args[0].stage == "Qualified"
    assert repo.update_status.await_args.kwargs["deal_attio_id"] == "deal-1"


@pytest.mark.asyncio
async def test_promote_does_not_regress_a_later_stage() -> None:
    gateway = _gateway(existing=[ExistingDeal("deal-1", "Old", "Diligence", None)])
    service, _, deals, _ = _service(update_result=_updated(), gateway=gateway)

    await service.approve_match(
        uuid4(), "U_TEST", resolution="promote_existing", existing_deal_id="deal-1"
    )

    gateway.promote_to_qualified.assert_not_awaited()
    assert deals.upsert.await_args.args[0].stage == "Diligence"


@pytest.mark.asyncio
async def test_create_new_skips_lookup() -> None:
    gateway = _gateway(existing=[ExistingDeal("deal-1", "Old", "Inbound", None)])
    service, _, _, _ = _service(update_result=_updated(), gateway=gateway)

    await service.approve_match(uuid4(), "U_TEST", resolution="create_new")

    gateway.find_pair_deals.assert_not_awaited()
    gateway.create_qualified.assert_awaited_once()


@pytest.mark.asyncio
async def test_attio_failure_saves_nothing() -> None:
    gateway = _gateway(create_error=DealGatewayError("boom"))
    service, repo, deals, _ = _service(update_result=_updated(), gateway=gateway)

    with pytest.raises(PartialWriteError) as raised:
        await service.approve_match(uuid4(), "U_TEST")

    assert raised.value.landed == []
    deals.upsert.assert_not_awaited()
    repo.update_status.assert_not_awaited()


@pytest.mark.asyncio
async def test_postgres_failure_reports_the_landed_deal() -> None:
    service, _, _, _ = _service(upsert_error=RuntimeError("db down"))

    with pytest.raises(PartialWriteError) as raised:
        await service.approve_match(uuid4(), "U_TEST")

    assert "deal-new" in raised.value.landed[0]


@pytest.mark.asyncio
async def test_approval_race_loser_reports_the_landed_deal() -> None:
    service, _, _, _ = _service(update_result=None)

    with pytest.raises(PartialWriteError) as raised:
        await service.approve_match(uuid4(), "U_TEST")

    assert isinstance(raised.value.cause, InvalidTransitionError)
    assert raised.value.landed


@pytest.mark.asyncio
async def test_terminal_match_is_rejected_before_any_attio_write() -> None:
    gateway = _gateway()
    service, _, _, _ = _service(gateway=gateway, candidate=_candidate(status="APPROVED"))

    with pytest.raises(InvalidTransitionError):
        await service.approve_match(uuid4(), "U_TEST")

    gateway.find_pair_deals.assert_not_awaited()


@pytest.mark.asyncio
async def test_promote_of_a_vanished_deal_reprompts_instead_of_creating() -> None:
    gateway = _gateway(existing=[ExistingDeal("deal-1", "Old", "Inbound", None)])
    service, _, _, _ = _service(update_result=_updated(), gateway=gateway)

    with pytest.raises(ExistingDealsFoundError):
        await service.approve_match(
            uuid4(), "U_TEST", resolution="promote_existing", existing_deal_id="gone"
        )

    gateway.create_qualified.assert_not_awaited()


@pytest.mark.asyncio
async def test_unstaged_existing_deal_keeps_its_missing_stage() -> None:
    gateway = _gateway(existing=[ExistingDeal("deal-1", "Old", None, None)])
    service, _, deals, _ = _service(update_result=_updated(), gateway=gateway)

    await service.approve_match(
        uuid4(), "U_TEST", resolution="promote_existing", existing_deal_id="deal-1"
    )

    assert deals.upsert.await_args.args[0].stage is None


@pytest.mark.asyncio
async def test_slow_attio_times_out_and_warns_the_deal_may_exist(monkeypatch) -> None:
    import asyncio

    from app.modules.matching_engine.application import approvals

    monkeypatch.setattr(approvals, "_ATTIO_WRITE_TIMEOUT_S", 0.01)

    async def slow(*_a, **_k):
        await asyncio.sleep(1)

    gateway = _gateway()
    gateway.create_qualified = slow
    service, _, deals, _ = _service(update_result=_updated(), gateway=gateway)

    with pytest.raises(PartialWriteError) as raised:
        await service.approve_match(uuid4(), "U_TEST")

    assert "may still have been created" in raised.value.landed[0]
    deals.upsert.assert_not_awaited()


@pytest.mark.asyncio
async def test_approval_records_one_event_linked_to_the_match_and_stamps_the_deal_actor() -> None:
    updated = _updated()
    service, _, deals, activities = _service(update_result=updated)

    await service.approve_match(uuid4(), "U_APPROVER")

    (call,) = activities.record.await_args_list
    event = call.args[0]
    assert event.event_type is EventType.MATCH_APPROVED
    assert event.actor.type is ActorType.SLACK_USER
    assert event.actor.ref == "U_APPROVER"
    assert (event.ledger.type, str(event.ledger.id)) == (LedgerType.MATCH_RESULT, updated.id)
    assert str(event.subject_uuid) == updated.buyer_role_id
    assert event.payload.deal_attio_id == "deal-new"
    assert event.idempotency_key == f"match.approved:{updated.id}"
    assert deals.upsert.await_args.kwargs["actor"].ref == "U_APPROVER"


@pytest.mark.asyncio
async def test_a_lost_approval_race_records_no_event() -> None:
    service, _, _, activities = _service(update_result=None)

    with pytest.raises(PartialWriteError):
        await service.approve_match(uuid4(), "U_TEST")

    activities.record.assert_not_awaited()


@pytest.mark.asyncio
async def test_rejection_records_one_event_linked_to_the_match() -> None:
    updated = _updated()
    service, repo, _, activities = _service(update_result=updated)
    repo.get_by_id = AsyncMock(return_value=_candidate())

    await service.reject_match(uuid4(), "U_REVIEWER")

    (call,) = activities.record.await_args_list
    event = call.args[0]
    assert event.event_type is EventType.MATCH_REJECTED
    assert event.actor.ref == "U_REVIEWER"
    assert (event.ledger.type, str(event.ledger.id)) == (LedgerType.MATCH_RESULT, updated.id)
    assert event.payload.deal_attio_id is None


@pytest.mark.asyncio
async def test_a_lost_rejection_race_records_no_event() -> None:
    service, repo, _, activities = _service(update_result=None)
    repo.get_by_id = AsyncMock(return_value=_candidate())

    with pytest.raises(InvalidTransitionError):
        await service.reject_match(uuid4(), "U_REVIEWER")

    activities.record.assert_not_awaited()
