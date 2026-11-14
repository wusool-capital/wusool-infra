"""Sign in with Slack for the web app: the signed session, the per-request
check, the shared-key fallback, and the OpenID callback."""

from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from pydantic import SecretStr

from app.modules.auth import SlackIdentity
from app.modules.matching_engine.api.http import auth, auth_routes, routes
from app.modules.matching_engine.api.http.session import (
    SESSION_COOKIE,
    WebSession,
    decode_session,
    encode_session,
)

_SECRET = "session-secret"
_TEAM = "T_WUSOOL"


def _settings(*, key: str | None = None, slack: bool = True) -> SimpleNamespace:
    return SimpleNamespace(
        web_api_key=SecretStr(key) if key else None,
        slack_client_id="client-id" if slack else None,
        slack_client_secret=SecretStr("client-secret") if slack else None,
        web_session_secret=SecretStr(_SECRET) if slack else None,
        web_public_url="https://tools.example" if slack else None,
        web_session_days=30,
        web_fallback_min_score=50.0,
        match_run_stale_after_minutes=15,
    )


def _session(**overrides: object) -> WebSession:
    now = datetime.now(UTC)
    fields = {
        "user_id": "U_ALICE",
        "team_id": _TEAM,
        "name": "Alice",
        "expires_at": now + timedelta(days=30),
        "checked_at": now,
    }
    return WebSession.model_validate({**fields, **overrides})


@pytest.fixture
def web(monkeypatch):
    service = SimpleNamespace(
        get_match_analysis=AsyncMock(return_value=None),
        get_seller_profiles=AsyncMock(return_value=[]),
        reject_match=AsyncMock(),
    )

    @asynccontextmanager
    async def _service():
        yield service

    state = SimpleNamespace(settings=_settings())
    for module in (auth, auth_routes, routes):
        monkeypatch.setattr(module, "get_settings", lambda: state.settings)
    monkeypatch.setattr(
        "app.modules.auth.providers.slack_identity.get_settings",
        lambda: state.settings,
    )
    monkeypatch.setattr(routes, "open_matching_engine_service", _service)
    monkeypatch.setattr(auth_routes, "workspace_team_id", AsyncMock(return_value=_TEAM))
    app = FastAPI()
    app.include_router(auth_routes.router)
    app.include_router(routes.router)
    client = TestClient(app, base_url="https://tools.example", follow_redirects=False)
    return SimpleNamespace(client=client, state=state, service=service)


def _sign_in(client: TestClient, session: WebSession | None = None) -> None:
    client.cookies.set(SESSION_COOKIE, encode_session(session or _session(), _SECRET))


def test_session_round_trips_and_rejects_tampering() -> None:
    now = datetime.now(UTC)
    session = _session()
    token = encode_session(session, _SECRET)

    decoded = decode_session(token, _SECRET, now=now)
    assert decoded is not None
    assert (decoded.user_id, decoded.team_id, decoded.name) == ("U_ALICE", _TEAM, "Alice")
    assert decoded.expires_at == session.expires_at
    assert decode_session(token, "other-secret", now=now) is None
    assert decode_session(token[:-2] + "xx", _SECRET, now=now) is None
    assert decode_session("garbage", _SECRET, now=now) is None


def test_expired_session_is_rejected() -> None:
    token = encode_session(_session(expires_at=datetime.now(UTC) - timedelta(seconds=1)), _SECRET)
    assert decode_session(token, _SECRET, now=datetime.now(UTC)) is None


def test_me_reports_the_signed_in_slack_user(web) -> None:
    _sign_in(web.client)

    body = web.client.get("/api/auth/me").json()

    assert body == {"slack_user_id": "U_ALICE", "name": "Alice", "via": "slack"}


def test_no_session_and_no_key_is_401(web) -> None:
    assert web.client.get("/api/auth/me").status_code == 401


def test_nothing_configured_is_503(web) -> None:
    web.state.settings = _settings(slack=False)

    assert web.client.get("/api/auth/me").status_code == 503


def test_shared_key_still_works_as_a_fallback(web) -> None:
    web.state.settings = _settings(key="local-key", slack=False)

    body = web.client.get("/api/auth/me", headers={"Authorization": "Bearer local-key"}).json()

    assert body["via"] == "key"


def test_a_cookie_write_without_the_client_header_is_refused(web) -> None:
    _sign_in(web.client)

    response = web.client.post(f"/api/match-runs/{uuid4()}/candidates/{uuid4()}/reject")

    assert response.status_code == 403


def test_a_decision_is_recorded_as_the_slack_user(web) -> None:
    candidate = SimpleNamespace(id=str(uuid4()))
    web.service.get_match_analysis.side_effect = [
        SimpleNamespace(run=SimpleNamespace(), candidates=[candidate], scores=[]),
        RuntimeError("stop after the decision"),
    ]
    _sign_in(web.client)

    with pytest.raises(RuntimeError):
        web.client.post(
            f"/api/match-runs/{uuid4()}/candidates/{candidate.id}/reject",
            headers={auth.CLIENT_HEADER: "web"},
        )

    assert web.service.reject_match.await_args.args[1] == "U_ALICE"


def test_a_day_old_session_is_rechecked_and_renewed(web, monkeypatch) -> None:
    check = AsyncMock(return_value=True)
    monkeypatch.setattr(auth, "is_active_member", check)
    _sign_in(web.client, _session(checked_at=datetime.now(UTC) - timedelta(days=2)))

    response = web.client.get("/api/auth/me")

    check.assert_awaited_once_with("U_ALICE")
    assert SESSION_COOKIE in response.cookies


def test_someone_removed_from_slack_is_signed_out(web, monkeypatch) -> None:
    monkeypatch.setattr(auth, "is_active_member", AsyncMock(return_value=False))
    _sign_in(web.client, _session(checked_at=datetime.now(UTC) - timedelta(days=2)))

    response = web.client.get("/api/auth/me")

    assert response.status_code == 401


def test_a_slack_outage_keeps_people_signed_in(web, monkeypatch) -> None:
    monkeypatch.setattr(auth, "is_active_member", AsyncMock(return_value=None))
    _sign_in(web.client, _session(checked_at=datetime.now(UTC) - timedelta(days=2)))

    assert web.client.get("/api/auth/me").status_code == 200


def test_login_sends_people_to_slack_for_our_workspace(web) -> None:
    response = web.client.get("/api/auth/slack/login", params={"next": "/app/runs/1"})

    location = response.headers["location"]
    assert location.startswith("https://slack.com/openid/connect/authorize?")
    assert f"team={_TEAM}" in location
    assert "redirect_uri=https%3A%2F%2Ftools.example%2Fapi%2Fauth%2Fslack%2Fcallback" in location
    assert "wusool_signin_state" in response.cookies


def _callback(web, monkeypatch, identity: SlackIdentity, *, next_path: str = "/app/runs/1"):
    monkeypatch.setattr(auth_routes, "identity_from_code", AsyncMock(return_value=identity))
    web.client.cookies.set("wusool_signin_state", f"abc|{next_path}", path="/api/auth")
    return web.client.get("/api/auth/slack/callback", params={"code": "c", "state": "abc"})


def test_callback_signs_in_and_returns_to_the_page(web, monkeypatch) -> None:
    response = _callback(web, monkeypatch, SlackIdentity("U_BOB", _TEAM, "Bob"))

    assert response.status_code == 303
    assert response.headers["location"] == "/app/runs/1"
    session = decode_session(response.cookies[SESSION_COOKIE], _SECRET, now=datetime.now(UTC))
    assert session is not None and session.user_id == "U_BOB"


def test_callback_refuses_another_workspace(web, monkeypatch) -> None:
    response = _callback(web, monkeypatch, SlackIdentity("U_EVE", "T_OTHER", "Eve"))

    assert "signin_error=wrong_workspace" in response.headers["location"]
    assert SESSION_COOKIE not in response.cookies


def test_callback_with_a_forged_state_is_refused(web, monkeypatch) -> None:
    monkeypatch.setattr(auth_routes, "identity_from_code", AsyncMock())
    web.client.cookies.set("wusool_signin_state", "real|/app/", path="/api/auth")

    response = web.client.get("/api/auth/slack/callback", params={"code": "c", "state": "forged"})

    assert "signin_error=expired" in response.headers["location"]
    auth_routes.identity_from_code.assert_not_awaited()


def test_callback_never_redirects_off_the_app(web, monkeypatch) -> None:
    response = _callback(
        web, monkeypatch, SlackIdentity("U_BOB", _TEAM, "Bob"), next_path="//evil.example"
    )

    assert response.headers["location"] == "/app/"
