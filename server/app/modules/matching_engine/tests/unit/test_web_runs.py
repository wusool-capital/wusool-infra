from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.matching_engine.api.http import web_runs
from app.modules.matching_engine.api.http.run_tracker import run_tracker


def _patch(monkeypatch, *, status: str, scores: list[float]):
    result = SimpleNamespace(
        status=status,
        notes=["note"],
        results=[SimpleNamespace(match_score=s) for s in scores],
    )
    service = SimpleNamespace(execute_run=AsyncMock(return_value=result))
    discover = AsyncMock()
    monkeypatch.setattr(
        web_runs, "detached_matching_engine_service", AsyncMock(return_value=service)
    )
    monkeypatch.setattr(
        web_runs, "get_settings", lambda: SimpleNamespace(web_fallback_min_score=50.0)
    )
    monkeypatch.setattr(web_runs, "discover_for_web_run", discover)
    return discover


@pytest.mark.asyncio
async def test_good_scores_skip_discovery(monkeypatch) -> None:
    discover = _patch(monkeypatch, status="GENERATED", scores=[80.0])
    started = SimpleNamespace(run_id=uuid4())

    await web_runs.execute_web_run(started, SimpleNamespace(), advisor_context=None)

    discover.assert_not_awaited()
    tracked = run_tracker.get(started.run_id)
    assert tracked is not None
    assert tracked.notes == ("note",)
    assert tracked.discovery is not None and tracked.discovery.status == "not_needed"


@pytest.mark.asyncio
async def test_low_scores_start_discovery(monkeypatch) -> None:
    discover = _patch(monkeypatch, status="GENERATED", scores=[10.0])
    started = SimpleNamespace(run_id=uuid4())

    await web_runs.execute_web_run(started, SimpleNamespace(), advisor_context=None)

    discover.assert_awaited_once_with(started.run_id)


@pytest.mark.asyncio
async def test_failed_run_never_starts_discovery(monkeypatch) -> None:
    discover = _patch(monkeypatch, status="FAILED", scores=[])

    await web_runs.execute_web_run(
        SimpleNamespace(run_id=uuid4()), SimpleNamespace(), advisor_context=None
    )

    discover.assert_not_awaited()
