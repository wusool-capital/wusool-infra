"""End-to-end Slack *block action* dispatch for `discover_add_seller` —
closes the gap between "the confirm-form hand-off is correct" and "the
wiring from a real Slack payload to that logic is correct". No live Slack
workspace, no database: every payload is hand-built to match Slack's real
`block_actions` shape, signed with the same HMAC scheme Slack really uses,
and `discovery_service()` is monkeypatched at its import site in
`app.modules.discovery.api.slack.handlers` so this file asserts the right
draft was handed to `SellerDraftPort`.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import app.modules.discovery.api.slack.handlers as handlers_module
from app.modules.discovery.api.dependencies import encode_lead
from app.modules.discovery.bootstrap import create_app
from app.modules.discovery.config import get_settings
from app.modules.discovery.domain.leads import DiscoveredLead

app = create_app()


class _FakeAuthTestResponse(dict):
    headers: dict = {}


@pytest.fixture(autouse=True)
def _mock_slack_auth(monkeypatch):
    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _post_interactivity(payload: dict) -> "TestClient":
    settings = get_settings()
    body = urlencode({"payload": json.dumps(payload)})
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)
    client = TestClient(app)
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )


def _block_action_payload(lead: DiscoveredLead) -> dict:
    return {
        "type": "block_actions",
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
        "trigger_id": "trigger.123",
        "actions": [{"action_id": "discover_add_seller", "value": encode_lead(lead)}],
    }


def test_discover_add_seller_opens_the_confirm_form_with_the_lead_mapped_to_a_draft(
    monkeypatch,
) -> None:
    calls: list[dict] = []

    class _FakeService:
        async def open_confirm_form(self, *, trigger_id, draft, channel_id, requested_by):
            calls.append(
                {
                    "trigger_id": trigger_id,
                    "draft": draft,
                    "channel_id": channel_id,
                    "requested_by": requested_by,
                }
            )

    monkeypatch.setattr(handlers_module, "discovery_service", lambda: _FakeService())

    lead = DiscoveredLead(
        name="Brand New Co", source_url="https://example.com", category="Retail / E-Commerce"
    )
    response = _post_interactivity(_block_action_payload(lead))

    assert response.status_code == 200
    assert len(calls) == 1
    assert calls[0]["trigger_id"] == "trigger.123"
    assert calls[0]["draft"].org_name == "Brand New Co"
    assert calls[0]["draft"].values == {"sector_focus": ["Retail / E-Commerce"]}
    assert calls[0]["channel_id"] == "C_TEST"


def test_discover_add_seller_reports_failure_without_crashing(monkeypatch) -> None:
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral", fake_chat_post_ephemeral
    )

    class _FailingService:
        async def open_confirm_form(self, **_kwargs):
            raise RuntimeError("Slack API error")

    monkeypatch.setattr(handlers_module, "discovery_service", lambda: _FailingService())

    lead = DiscoveredLead(name="Brand New Co", source_url="https://example.com")
    response = _post_interactivity(_block_action_payload(lead))

    assert response.status_code == 200
    assert "Couldn't process" in posted[0]["text"]


def test_discover_add_seller_reports_a_malformed_button_value_without_crashing(
    monkeypatch,
) -> None:
    """A stale/legacy button value (e.g. after a deploy changes
    `DiscoveredLead`'s shape) must surface an ephemeral message, not fail
    silently after `ack()` has already fired.
    """
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral", fake_chat_post_ephemeral
    )

    payload = {
        "type": "block_actions",
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
        "trigger_id": "trigger.123",
        "actions": [{"action_id": "discover_add_seller", "value": "not valid json"}],
    }
    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert "Couldn't process" in posted[0]["text"]
