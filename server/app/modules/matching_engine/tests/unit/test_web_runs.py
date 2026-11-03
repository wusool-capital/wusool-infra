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


@pytest.mark.asyncio
async def test_sellers_created_but_not_attached_say_so(monkeypatch) -> None:
    import app.modules.discovery as discovery_module
    from app.modules.matching_engine.application import discovery_bridge

    run_id = uuid4()
    service = SimpleNamespace(
        get_match_analysis=AsyncMock(
            return_value=SimpleNamespace(
                run=SimpleNamespace(requirement_profile=object(), buyer_role_id=uuid4())
            )
        ),
        append_discovered_candidates=AsyncMock(side_effect=RuntimeError("db down")),
    )
    created = SimpleNamespace(
        seller_role_id=uuid4(), org_attio_id="org-1", source_url="https://maps", org_name="Acme"
    )
    outcome = SimpleNamespace(status="ok", created=(created,))
    monkeypatch.setattr(
        web_runs, "detached_matching_engine_service", AsyncMock(return_value=service)
    )
    monkeypatch.setattr(
        discovery_bridge, "extract_query_terms", lambda _profile: ("clinics", "Riyadh", [])
    )
    monkeypatch.setattr(
        discovery_module, "discover_and_create_sellers", AsyncMock(return_value=outcome)
    )
    monkeypatch.setattr(web_runs, "discovery_outcome_notes", lambda _o: [])

    result = await web_runs._discover(run_id)

    assert result.status == "failed"
    assert "Created 1 seller(s) in the CRM (Acme)" in (result.message or "")
