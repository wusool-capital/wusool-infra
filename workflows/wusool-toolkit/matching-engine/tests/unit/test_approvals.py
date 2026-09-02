from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.approvals.application.use_cases import (
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
    def begin():
        return _AsyncContextManager()

    session = SimpleNamespace(begin=begin, repo=repo)

    def sessionmaker():
        return _AsyncContextManager(session)

    # The use case constructs the repository itself; replace that boundary
    # with the scripted compare-and-set result for this unit test.
    import app.modules.approvals.application.use_cases as module

    monkeypatch = pytest.MonkeyPatch()
    monkeypatch.setattr(module, "MatchResultRepository", lambda _session: repo)
    try:
        with pytest.raises(InvalidTransitionError):
            await ApproveMatchUseCase(cast(async_sessionmaker, sessionmaker)).execute(
                uuid4(), "U_TEST"
            )
    finally:
        monkeypatch.undo()


class _AsyncContextManager:
    def __init__(self, value=None):
        self.value = value

    async def __aenter__(self):
        return self.value

    async def __aexit__(self, *_args):
        return False
