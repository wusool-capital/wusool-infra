"""Slack command -> acknowledgement -> usage-message dispatch, without an
actual Slack workspace. Signs the request the way Slack really does
(HMAC-SHA256 over `v0:<timestamp>:<body>`) so Bolt's real signature
verification is exercised, not bypassed. The Slack Web API client is
monkeypatched — no network calls leave the process. Mirrors
`ddl_commands`'/`matching_engine`'s own `test_slack_command_dispatch.py`.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient

from app.modules.enrichment.api.slack.handlers import commands as commands_module
from app.modules.enrichment.bootstrap import create_app
from app.modules.enrichment.config import get_settings
from app.modules.enrichment.domain.targets import ResolvedOrgRole

app = create_app()


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def test_enrich_seller_with_no_text_posts_seller_scoped_usage(monkeypatch) -> None:
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral",
        fake_chat_post_ephemeral,
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)

    settings = get_settings()
    body = urlencode(
        {
            "command": "/enrich-seller",
            "text": "",
            "channel_id": "C_TEST",
            "user_id": "U_TEST",
            "trigger_id": "trigger.123",
        }
    )
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)

    client = TestClient(app)
    response = client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "/enrich-seller <seller name>" in posted[0]["text"]


def test_enrich_seller_ignores_a_buyer_only_match(monkeypatch) -> None:
    """An org with only a buyer role must not be treated as a candidate for
    `/enrich-seller` — the kind filter should leave zero candidates, not
    silently fall through to enriching the buyer role.
    """
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    async def fake_resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
        return [
            ResolvedOrgRole(
                org_attio_id="org-1", org_name="Blue Horizon", role_id="role-1", kind="buyer"
            )
        ]

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral",
        fake_chat_post_ephemeral,
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)
    monkeypatch.setattr(commands_module, "resolve_org_roles", fake_resolve_org_roles)

    settings = get_settings()
    body = urlencode(
        {
            "command": "/enrich-seller",
            "text": "Blue Horizon",
            "channel_id": "C_TEST",
            "user_id": "U_TEST",
            "trigger_id": "trigger.456",
        }
    )
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)

    client = TestClient(app)
    response = client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "No active seller found for *Blue Horizon*" in posted[0]["text"]


def test_enrich_buyer_with_no_text_posts_buyer_scoped_usage(monkeypatch) -> None:
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral",
        fake_chat_post_ephemeral,
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)

    settings = get_settings()
    body = urlencode(
        {
            "command": "/enrich-buyer",
            "text": "",
            "channel_id": "C_TEST",
            "user_id": "U_TEST",
            "trigger_id": "trigger.789",
        }
    )
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)

    client = TestClient(app)
    response = client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "/enrich-buyer <buyer name>" in posted[0]["text"]


def test_enrich_buyer_ignores_a_seller_only_match(monkeypatch) -> None:
    """Mirror of `test_enrich_seller_ignores_a_buyer_only_match` — an org
    with only a seller role must not be treated as a candidate for
    `/enrich-buyer`.
    """
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    async def fake_resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
        return [
            ResolvedOrgRole(
                org_attio_id="org-2", org_name="Acme Rollup", role_id="role-2", kind="seller"
            )
        ]

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral",
        fake_chat_post_ephemeral,
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)
    monkeypatch.setattr(commands_module, "resolve_org_roles", fake_resolve_org_roles)

    settings = get_settings()
    body = urlencode(
        {
            "command": "/enrich-buyer",
            "text": "Acme Rollup",
            "channel_id": "C_TEST",
            "user_id": "U_TEST",
            "trigger_id": "trigger.101",
        }
    )
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)

    client = TestClient(app)
    response = client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "No active buyer found for *Acme Rollup*" in posted[0]["text"]
