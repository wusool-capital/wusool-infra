"""Request validation on the HTTP surface.

Scope note. These deliberately cover only what needs no database, because
`TestClient` runs the app in an event-loop portal of its own and the async
engine is `lru_cache`d — mixing the two against a real database produces
"attached to a different loop", and working around it with cache clearing
breaks the tests that share the engine. The DB-backed write contract is
covered at the service level in `test_write_contract_e2e.py`, which uses the
real session and the real SQL.

Validation is worth testing here in its own right: these four pages are
being rewritten to post structured data instead of composing prompts, so a
misspelled field must fail loudly rather than be dropped and scored as a
blank.

Two behaviours found only by driving the endpoints with curl, and fixed,
are asserted where they can be reached without a database:
  - an unknown `peer_key` is a 422 from request validation, not a 500 out of
    the scoring engine (which also lost the lead, since scoring ran first);
  - unknown fields are rejected rather than silently ignored.
"""

import uuid

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.modules.lead_magnets.api.router import router


@pytest.fixture(scope="module")
def client():
    app = FastAPI()
    app.include_router(router)
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


def _payload(**overrides) -> dict:
    # A fresh email/domain per call, not just a fresh submission_id: the
    # idempotency key is now `tool|email|domain` alone (no submission_id),
    # so several calls sharing one identity — as every caller of this
    # helper used to, safely, when submission_id made each one unique —
    # would collide and get rejected as a repeat instead of validated fresh.
    unique = uuid.uuid4().hex[:8]
    body = {
        "submission_id": str(uuid.uuid4()),
        "peer_key": "restaurant",
        "company": "Acme Restaurant Group LLC",
        "email": f"dana+{unique}@acmegroup.ae",
        "domain": f"https://www.acmegroup-{unique}.ae/about",
        "revenue": 3_000_000,
        "headcount": 40,
    }
    return {**body, **overrides}


def test_an_unknown_peer_key_is_rejected_before_scoring(client) -> None:
    """A 422 naming the field, not a 500 out of the scoring engine.

    Rejected during request validation, so the handler never runs — which is
    also why the lead cannot be lost to it. Before this, `evaluate()` ran
    ahead of `record()` and a bad sector key returned a 500 with nothing
    written at all.
    """
    response = client.post("/benchmark", json=_payload(peer_key="not_a_sector"))

    assert response.status_code == 422
    detail = response.json()["detail"][0]
    assert detail["loc"] == ["body", "peer_key"]
    assert "unknown peer_key" in detail["msg"]
    # The message names the valid options, so a page bug is self-diagnosing.
    assert "restaurant" in detail["msg"]


@pytest.mark.parametrize("peer_key", ["restaurant", "ecommerce", "manufacturing"])
def test_known_sectors_pass_validation(client, peer_key: str) -> None:
    """The validator must not reject the real dataset keys. It runs before
    any database work, so a 422 here would be a validation bug and anything
    else means it passed."""
    response = client.post("/benchmark", json=_payload(peer_key=peer_key))
    assert response.status_code != 422


@pytest.mark.parametrize("stage", ["seed", "seriesa", "seriesb"])
def test_startup_stages_pass_validation(client, stage: str) -> None:
    response = client.post("/benchmark", json=_payload(mode="tech", peer_key=stage))
    assert response.status_code != 422


def test_unknown_fields_are_rejected_not_silently_dropped(client) -> None:
    """These pages are being rewritten; a misspelled field must fail loudly
    rather than score as a blank."""
    response = client.post("/benchmark", json=_payload(revenu=3_000_000))
    assert response.status_code == 422
    assert any(d["loc"][-1] == "revenu" for d in response.json()["detail"])


def test_missing_required_fields_are_rejected(client) -> None:
    response = client.post("/benchmark", json={})
    assert response.status_code == 422
    missing = {tuple(d["loc"]) for d in response.json()["detail"]}
    assert ("body", "submission_id") in missing
    assert ("body", "peer_key") in missing
    assert ("body", "email") in missing


@pytest.mark.parametrize("answer", [-1, 4, 99])
def test_out_of_range_questionnaire_answers_are_rejected(client, answer: int) -> None:
    """0-3 is the scored range; anything else would be ranked as if it were a
    real answer."""
    response = client.post(
        "/readiness/score",
        json={
            "submission_id": str(uuid.uuid4()),
            "name": "Sam",
            "company": "Beta Trading FZ-LLC",
            "email": "sam@betatrading.ae",
            "sector": "Contracting",
            "answers": {"q1": answer},
        },
    )
    assert response.status_code == 422


def test_percentage_fields_reject_impossible_values(client) -> None:
    assert client.post("/benchmark", json=_payload(top_customer_pct=140)).status_code == 422
    assert client.post("/benchmark", json=_payload(recurring_pct=-5)).status_code == 422


def test_negative_revenue_is_rejected(client) -> None:
    assert client.post("/benchmark", json=_payload(revenue=-1)).status_code == 422


def _valuation_payload(**overrides) -> dict:
    # See `_payload`'s comment: a fresh identity per call, not just a fresh
    # submission_id, now that the idempotency key no longer carries one.
    unique = uuid.uuid4().hex[:8]
    body = {
        "submission_id": str(uuid.uuid4()),
        "company": "Acme Restaurant Group LLC",
        "email": f"dana+{unique}@acmegroup.ae",
        "domain": f"acmegroup-{unique}.ae",
        "revenue": 3_000_000,
        "profit_before_tax": 400_000,
    }
    return {**body, **overrides}


def test_submit_lead_missing_required_fields_are_rejected(client) -> None:
    response = client.post("/submit-lead", json={})
    assert response.status_code == 422
    missing = {tuple(d["loc"]) for d in response.json()["detail"]}
    assert ("body", "submission_id") in missing
    assert ("body", "company") in missing
    assert ("body", "email") in missing
    assert ("body", "revenue") in missing


def test_submit_lead_negative_revenue_is_rejected(client) -> None:
    assert client.post("/submit-lead", json=_valuation_payload(revenue=-1)).status_code == 422


def test_submit_lead_unknown_top_level_field_is_rejected(client) -> None:
    response = client.post("/submit-lead", json=_valuation_payload(revenuee=1))
    assert response.status_code == 422
    assert any(d["loc"][-1] == "revenuee" for d in response.json()["detail"])


def test_submit_lead_with_comps_and_discounts_passes_validation(client) -> None:
    """The shapes `/compare` and `/analyze` actually return, round-tripped
    back in verbatim — must not be rejected."""
    response = client.post(
        "/submit-lead",
        json=_valuation_payload(
            comps=[
                {"co": "Talabat PLC", "tk": "TALABAT", "ev": 10_000, "rev": 1_900, "ebitda": 380}
            ],
            discounts={"revenue_discount_pct": 45.0, "ebitda_discount_pct": 40.0},
        ),
    )
    assert response.status_code != 422
