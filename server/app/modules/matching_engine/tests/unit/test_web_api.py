from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.modules.matching_engine.api.buyers import BuyerSummary, _BuyerCandidateOrg
from app.modules.matching_engine.api.http import auth, routes
from app.modules.matching_engine.api.http.run_tracker import TrackedDiscovery, run_tracker
from app.modules.matching_engine.application.approvals import InvalidTransitionError
from app.modules.matching_engine.application.errors import ExistingDealsFoundError
from app.modules.matching_engine.domain.matching.deals import ExistingDeal

_KEY = "test-web-key"
_HEADERS = {"Authorization": f"Bearer {_KEY}"}


def _settings(key: str | None = _KEY):
    return SimpleNamespace(
        web_api_key=SecretStr(key) if key is not None else None,
        web_fallback_min_score=50.0,
        match_run_stale_after_minutes=15,
    )


def _row(**overrides):
    fields = {
        "id": str(uuid4()), "run_id": str(uuid4()), "rank": 1, "status": "PENDING_REVIEW",
        "buyer_attio_id": "buyer-1", "buyer_role_id": str(uuid4()), "buyer_org_name": "Buyer Co",
        "seller_attio_id": "seller-1", "seller_role_id": str(uuid4()),
        "seller_org_name": "Seller Co", "match_score": 82.0, "data_confidence": 0.7,
        "why_chosen_over_alternatives": "=cmd()", "recommended_pitch": "Pitch",
        "risks_and_gaps": None, "decision": None, "decided_at": None, "deal_attio_id": None,
        "errors": None, "started_at": datetime.now(UTC), "completed_at": datetime.now(UTC),
        "candidates_considered": 10, "candidates_filtered": 4, "origin": "crm",
        "source_url": None,
    }  # fmt: skip
    return SimpleNamespace(**{**fields, **overrides})


def _analysis(*, run=None, candidates=None):
    run = run or _row(rank=None, status="GENERATED")
    candidates = candidates if candidates is not None else [_row(run_id=run.run_id)]
    scores = [SimpleNamespace(seller_attio_id="seller-1", reasoning="Strong sector fit")]
    return SimpleNamespace(run=run, candidates=candidates, scores=scores)


@pytest.fixture
def api(monkeypatch):
    service = SimpleNamespace(
        get_match_analysis=AsyncMock(return_value=None),
        start_run=AsyncMock(),
        approve_match=AsyncMock(),
        reject_match=AsyncMock(),
    )
    runner = MagicMock()

    async def _service():
        return service

    monkeypatch.setattr(routes, "detached_matching_engine_service", _service)
    monkeypatch.setattr(routes, "_task_runner", runner)
    monkeypatch.setattr(routes, "get_settings", lambda: _settings())
    monkeypatch.setattr(auth, "get_settings", lambda: _settings())
    app = FastAPI()
    app.include_router(routes.router)
    return SimpleNamespace(client=TestClient(app), service=service, runner=runner)


def test_missing_key_is_401(api) -> None:
    response = api.client.get("/api/buyers", params={"q": "acme"})

    assert response.status_code == 401
    assert response.json()["detail"]["code"] == "unauthorized"


def test_wrong_key_is_401(api) -> None:
    response = api.client.get(
        "/api/buyers", params={"q": "acme"}, headers={"Authorization": "Bearer nope"}
    )

    assert response.status_code == 401


def test_unset_key_disables_api(api, monkeypatch) -> None:
    monkeypatch.setattr(auth, "get_settings", lambda: _settings(None))

    response = api.client.get("/api/buyers", params={"q": "acme"}, headers=_HEADERS)

    assert response.status_code == 503
    assert response.json()["detail"]["code"] == "web_disabled"


def test_search_buyers_returns_summaries(api, monkeypatch) -> None:
    summary = BuyerSummary(id="b1", organization=_BuyerCandidateOrg(name="Acme"))
    monkeypatch.setattr(
        routes,
        "resolve_buyer",
        AsyncMock(return_value=SimpleNamespace(status="single", candidates=[summary])),
    )

    response = api.client.get("/api/buyers", params={"q": "acme"}, headers=_HEADERS)

    assert response.status_code == 200
    assert response.json()[0]["organization"]["name"] == "Acme"


def test_preflight_unknown_buyer_is_404(api, monkeypatch) -> None:
    monkeypatch.setattr(routes, "find_buyer_discrepancies", AsyncMock(return_value=None))

    response = api.client.post(f"/api/buyers/{uuid4()}/preflight", json={}, headers=_HEADERS)

    assert response.status_code == 404


def test_preflight_returns_structured_report(api, monkeypatch) -> None:
    missing = SimpleNamespace(
        criterion=SimpleNamespace(value="ticket_band"), stored="", stated=None
    )
    context = SimpleNamespace(
        verticals=("healthcare",), region="GCC", countries=(), ticket_low=1e6, ticket_high=None,
        ebitda_low=None, ebitda_high=None, ev_ceiling=None, revenue_low=None, revenue_high=None,
        seller_status=(),
    )  # fmt: skip
    result = SimpleNamespace(
        report=SimpleNamespace(conflicts=(), missing=(missing,)),
        context_checked=True,
        context=context,
    )
    monkeypatch.setattr(routes, "find_buyer_discrepancies", AsyncMock(return_value=result))

    response = api.client.post(
        f"/api/buyers/{uuid4()}/preflight", json={"advisor_context": "GCC"}, headers=_HEADERS
    )

    body = response.json()
    assert body["missing"][0]["criterion"] == "ticket_band"
    assert body["context"]["verticals"] == ["healthcare"]


def test_start_run_is_202_and_schedules_execution(api, monkeypatch) -> None:
    run_id = uuid4()
    api.service.start_run.return_value = SimpleNamespace(run_id=run_id)
    monkeypatch.setattr(routes, "resolve_buyer_by_id", AsyncMock(return_value=SimpleNamespace()))

    response = api.client.post(
        "/api/match-runs", json={"buyer_role_id": str(uuid4())}, headers=_HEADERS
    )

    assert response.status_code == 202
    assert response.json() == {"run_id": str(run_id)}
    api.runner.run.assert_called_once()


def test_start_run_unknown_buyer_is_404(api, monkeypatch) -> None:
    monkeypatch.setattr(routes, "resolve_buyer_by_id", AsyncMock(return_value=None))

    response = api.client.post(
        "/api/match-runs", json={"buyer_role_id": str(uuid4())}, headers=_HEADERS
    )

    assert response.status_code == 404
    api.runner.run.assert_not_called()


def test_unknown_run_is_404(api) -> None:
    response = api.client.get(f"/api/match-runs/{uuid4()}", headers=_HEADERS)

    assert response.status_code == 404
    assert response.json()["detail"]["code"] == "not_found"


def test_completed_run_carries_candidates_and_reasoning(api) -> None:
    api.service.get_match_analysis.return_value = _analysis()

    body = api.client.get(f"/api/match-runs/{uuid4()}", headers=_HEADERS).json()

    assert body["state"] == "completed"
    assert body["low_match_quality"] is False
    assert body["discovery_threshold"] == 50.0
    assert body["discovery"]["status"] == "not_needed"
    assert body["candidates"][0]["why_it_matches"] == "Strong sector fit"


def test_lost_run_reads_as_stale(api) -> None:
    run = _row(rank=None, completed_at=None, started_at=datetime.now(UTC) - timedelta(hours=1))
    api.service.get_match_analysis.return_value = _analysis(run=run, candidates=[])

    body = api.client.get(f"/api/match-runs/{uuid4()}", headers=_HEADERS).json()

    assert body["state"] == "stale"


def test_low_scores_report_tracked_discovery(api) -> None:
    run_id = uuid4()
    candidate = _row(match_score=20.0)
    api.service.get_match_analysis.return_value = _analysis(candidates=[candidate])
    run_tracker.set_discovery(run_id, TrackedDiscovery(status="running"))

    body = api.client.get(f"/api/match-runs/{run_id}", headers=_HEADERS).json()

    assert body["low_match_quality"] is True
    assert body["discovery"]["status"] == "running"


def test_low_scores_without_tracker_offer_manual_discovery(api) -> None:
    api.service.get_match_analysis.return_value = _analysis(candidates=[_row(match_score=20.0)])

    body = api.client.get(f"/api/match-runs/{uuid4()}", headers=_HEADERS).json()

    assert body["discovery"]["status"] == "available"


def test_manual_discovery_schedules_search(api) -> None:
    api.service.get_match_analysis.return_value = _analysis()

    response = api.client.post(f"/api/match-runs/{uuid4()}/discovery", headers=_HEADERS)

    assert response.status_code == 202
    api.runner.run.assert_called_once()


def test_manual_discovery_on_running_run_is_409(api) -> None:
    api.service.get_match_analysis.return_value = _analysis(run=_row(rank=None, completed_at=None))

    response = api.client.post(f"/api/match-runs/{uuid4()}/discovery", headers=_HEADERS)

    assert response.status_code == 409


def test_approve_records_web_actor(api) -> None:
    candidate = _row()
    decided = _row(id=candidate.id, status="APPROVED", decision="APPROVED")
    api.service.get_match_analysis.side_effect = [
        _analysis(candidates=[candidate]),
        _analysis(candidates=[decided]),
    ]

    response = api.client.post(
        f"/api/match-runs/{uuid4()}/candidates/{candidate.id}/approve", json={}, headers=_HEADERS
    )

    assert response.status_code == 200
    assert response.json()["candidate"]["status"] == "APPROVED"
    assert api.service.approve_match.await_args.args[1] == "web"


def test_approve_with_existing_deals_is_409_with_choices(api) -> None:
    candidate = _row()
    api.service.get_match_analysis.return_value = _analysis(candidates=[candidate])
    api.service.approve_match.side_effect = ExistingDealsFoundError(
        [ExistingDeal("deal-1", "Old deal", "Inbound", None)]
    )

    response = api.client.post(
        f"/api/match-runs/{uuid4()}/candidates/{candidate.id}/approve", json={}, headers=_HEADERS
    )

    detail = response.json()["detail"]
    assert response.status_code == 409
    assert detail["code"] == "existing_deals"
    assert detail["existing_deals"][0]["attio_id"] == "deal-1"


def test_approve_passes_deal_choice(api) -> None:
    candidate = _row()
    api.service.get_match_analysis.return_value = _analysis(candidates=[candidate])

    api.client.post(
        f"/api/match-runs/{uuid4()}/candidates/{candidate.id}/approve",
        json={"resolution": "promote_existing", "existing_deal_id": "deal-1"},
        headers=_HEADERS,
    )

    kwargs = api.service.approve_match.await_args.kwargs
    assert kwargs == {"resolution": "promote_existing", "existing_deal_id": "deal-1"}


def test_candidate_from_another_run_is_404(api) -> None:
    api.service.get_match_analysis.return_value = _analysis()

    response = api.client.post(
        f"/api/match-runs/{uuid4()}/candidates/{uuid4()}/reject", headers=_HEADERS
    )

    assert response.status_code == 404
    api.service.reject_match.assert_not_awaited()


def test_reject_already_reviewed_is_409(api) -> None:
    candidate = _row()
    api.service.get_match_analysis.return_value = _analysis(candidates=[candidate])
    api.service.reject_match.side_effect = InvalidTransitionError("decided")

    response = api.client.post(
        f"/api/match-runs/{uuid4()}/candidates/{candidate.id}/reject", headers=_HEADERS
    )

    assert response.status_code == 409
    assert response.json()["detail"]["code"] == "already_reviewed"


def test_export_csv_neutralises_formulas(api) -> None:
    api.service.get_match_analysis.return_value = _analysis()

    response = api.client.get(f"/api/match-runs/{uuid4()}/export.csv", headers=_HEADERS)

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    lines = response.text.splitlines()
    assert lines[0].startswith("rank,origin,seller")
    assert "'=cmd()" in lines[1]


def test_export_csv_keeps_only_requested_fields_in_order(api) -> None:
    api.service.get_match_analysis.return_value = _analysis()

    response = api.client.get(
        f"/api/match-runs/{uuid4()}/export.csv",
        params=[("fields", "match_score"), ("fields", "seller"), ("fields", "match_score")],
        headers=_HEADERS,
    )

    assert response.status_code == 200
    rows = response.text.splitlines()
    assert rows[0] == "match_score,seller"
    assert all(row.count(",") == 1 for row in rows[1:])


def test_export_csv_rejects_unknown_field(api) -> None:
    api.service.get_match_analysis.return_value = _analysis()

    response = api.client.get(
        f"/api/match-runs/{uuid4()}/export.csv", params={"fields": "password"}, headers=_HEADERS
    )

    assert response.status_code == 422
