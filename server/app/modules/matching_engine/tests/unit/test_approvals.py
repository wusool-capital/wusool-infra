from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.matching_engine.application.approvals import (
    ApproveMatchUseCase,
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

    with pytest.raises(InvalidTransitionError):
        await ApproveMatchUseCase(uow_factory).execute(uuid4(), "U_TEST")


class _AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False
