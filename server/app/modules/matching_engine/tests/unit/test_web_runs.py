from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from app.modules.matching_engine.api import dependencies as deps
from app.modules.matching_engine.api.dependencies import RunDiscovery
from app.modules.matching_engine.api.http import web_runs
from app.modules.matching_engine.api.http.run_tracker import TrackedDiscovery, run_tracker


def _patch(monkeypatch, *, status: str, scores: list[float]):
    result = SimpleNamespace(
        status=status,
        notes=["note"],
        results=[SimpleNamespace(match_score=s) for s in scores],
    )
    service = SimpleNamespace(execute_run=AsyncMock(return_value=result))
    discover = AsyncMock()

    @asynccontextmanager
    async def _open():
        yield service

    monkeypatch.setattr(web_runs, "open_matching_engine_service", _open)
    monkeypatch.setattr(deps, "get_settings", lambda: SimpleNamespace(web_fallback_min_score=50.0))
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


def _created(name: str = "Acme") -> SimpleNamespace:
    return SimpleNamespace(seller_role_id=uuid4(), org_name=name)


@pytest.mark.asyncio
async def test_web_reports_the_shared_search_outcome(monkeypatch) -> None:
    run_id = uuid4()
    seen_running: list[str | None] = []

    async def fake_search(_run_id, *, on_search_start):
        await on_search_start()
        tracked = run_tracker.get(_run_id)
        seen_running.append(tracked.discovery.status if tracked and tracked.discovery else None)
        return RunDiscovery(
            kind="setup_failed",
            outcome=SimpleNamespace(status="ok", created=(_created(),)),
            notes=("2 more already in the CRM.",),
        )

    monkeypatch.setattr(web_runs, "discover_sellers_for_run", fake_search)

    await web_runs.discover_for_web_run(run_id)

    assert seen_running == ["running"]
    tracked = run_tracker.get(run_id)
    assert tracked is not None and tracked.discovery is not None
    assert tracked.discovery.status == "failed"
    assert "Created 1 seller(s) in the CRM (Acme)" in (tracked.discovery.message or "")
    assert tracked.discovery.notes == ("2 more already in the CRM.",)


@pytest.mark.asyncio
async def test_a_search_held_elsewhere_defers_to_the_run_row(monkeypatch) -> None:
    run_id = uuid4()
    run_tracker.set_discovery(run_id, TrackedDiscovery(status="running"))
    monkeypatch.setattr(
        web_runs,
        "discover_sellers_for_run",
        AsyncMock(return_value=RunDiscovery(kind="duplicate")),
    )

    await web_runs.discover_for_web_run(run_id)

    tracked = run_tracker.get(run_id)
    assert tracked is not None and tracked.discovery is None


@pytest.mark.asyncio
async def test_a_crash_reads_as_a_failed_search(monkeypatch) -> None:
    run_id = uuid4()
    monkeypatch.setattr(
        web_runs, "discover_sellers_for_run", AsyncMock(side_effect=RuntimeError("boom"))
    )

    await web_runs.discover_for_web_run(run_id)

    tracked = run_tracker.get(run_id)
    assert tracked is not None and tracked.discovery is not None
    assert tracked.discovery.status == "failed"
    assert tracked.discovery.message == "Seller search failed unexpectedly."
