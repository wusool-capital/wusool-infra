"""Slack command -> acknowledgement -> usage-message dispatch, without an
actual Slack workspace. Signs the request the way Slack really does
(HMAC-SHA256 over `v0:<timestamp>:<body>`) so Bolt's real signature
verification is exercised, not bypassed. The Slack Web API client is
monkeypatched — no network calls leave the process. Mirrors matching-engine's
`test_slack_command_dispatch.py` pattern exactly.
"""

import hashlib
import hmac
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

from app.modules.ddl_commands.bootstrap import create_app
from app.modules.ddl_commands.config import get_settings

app = create_app()


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


@pytest.mark.parametrize("command", ["/edit-seller", "/edit-buyer", "/add-seller", "/add-buyer"])
def test_command_with_no_text_posts_usage_without_touching_db(command: str, monkeypatch) -> None:
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
            "command": command,
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
    assert "Usage" in posted[0]["text"]
