from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import UUID, uuid4

import pytest

from app.modules.matching_engine.application.matching.use_cases import MatchingMixin

_HEADER_ID = str(uuid4())


class _AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False


def _buyer():
    return SimpleNamespace(buyer_role_id=str(uuid4()), org_attio_id="buyer-1", org_name="Buyer Co")


def _service():
    repo = SimpleNamespace(
        create_run=AsyncMock(return_value=SimpleNamespace(id=_HEADER_ID)),
        get_latest_requirement_profile_version=AsyncMock(side_effect=RuntimeError("boom")),
        complete_run=AsyncMock(),
    )
    activities = SimpleNamespace(record=AsyncMock())
    uow = SimpleNamespace(match_results=repo, activities=activities)
    service = MatchingMixin(
        lambda: _AsyncContextManager(uow),
        buyer_repository=SimpleNamespace(),
        extraction_service=SimpleNamespace(),
        reasoning_service=SimpleNamespace(),
        candidate_retriever=SimpleNamespace(),
        scoring_engine=SimpleNamespace(),
        top_n=3,
        deal_gateway=SimpleNamespace(),
    )
    return service, repo


@pytest.mark.asyncio
async def test_start_run_commits_header_and_returns_run_id() -> None:
    service, repo = _service()
    buyer = _buyer()

    started = await service.start_run(buyer, "U_TEST")

    kwargs = repo.create_run.await_args.kwargs
    assert kwargs["run_id"] == started.run_id
    assert kwargs["buyer_role_id"] == UUID(buyer.buyer_role_id)
    assert kwargs["requested_by"] == "U_TEST"
    assert started.header_row_id == _HEADER_ID
    repo.complete_run.assert_not_awaited()


@pytest.mark.asyncio
async def test_execute_run_marks_failed_run_on_error() -> None:
    service, repo = _service()
    buyer = _buyer()
    started = await service.start_run(buyer, None)

    result = await service.execute_run(started, buyer, None)

    assert result.status == "FAILED"
    assert result.run_id == str(started.run_id)
    assert repo.complete_run.await_args.kwargs["status"] == "FAILED"


@pytest.mark.asyncio
async def test_run_match_still_runs_both_phases() -> None:
    service, repo = _service()

    result = await service.run_match(_buyer(), "U_TEST")

    repo.create_run.assert_awaited_once()
    assert result.status == "FAILED"
    assert repo.complete_run.await_args.args[0] == UUID(result.run_id)
