from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.matching_engine.application.approvals import (
    ApprovalsMixin,
    InvalidTransitionError,
)


@pytest.mark.asyncio
async def test_approval_race_loser_raises_invalid_transition() -> None:
    candidate = SimpleNamespace(status="PENDING_REVIEW")
    repo = SimpleNamespace(
        get_by_id=AsyncMock(return_value=candidate),
        update_status=AsyncMock(return_value=None),
    )
    uow = SimpleNamespace(match_results=repo)

    def uow_factory():
        return _AsyncContextManager(uow)

    # Only approve_match/reject_match are exercised here — the other
    # ServiceBase dependencies are unused by this mixin's methods, so
    # SimpleNamespace() stand-ins are enough (no Protocol conformance
    # needed at runtime).
    service = ApprovalsMixin(
        uow_factory,
        buyer_repository=SimpleNamespace(),
        extraction_service=SimpleNamespace(),
        reasoning_service=SimpleNamespace(),
        candidate_retriever=SimpleNamespace(),
        scoring_engine=SimpleNamespace(),
        top_n=0,
    )

    with pytest.raises(InvalidTransitionError):
        await service.approve_match(uuid4(), "U_TEST")


class _AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False
