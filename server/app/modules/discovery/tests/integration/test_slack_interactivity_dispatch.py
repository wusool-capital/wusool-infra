"""End-to-end Slack *block action* dispatch for `discover_add_seller` —
closes the gap between "the confirm-form hand-off is correct" and "the
wiring from a real Slack payload to that logic is correct". No live Slack
workspace, no database: every payload is hand-built to match Slack's real
`block_actions` shape, signed with the same HMAC scheme Slack really uses,
and `discovery_service()` is monkeypatched at its import site in
`app.modules.discovery.api.slack.handlers` so this file asserts the right
draft was handed to `SellerDraftPort`.
"""

import pytest

import app.modules.discovery.api.slack.handlers as handlers_module
from app.modules.discovery.api.dependencies import encode_draft
from app.modules.discovery.bootstrap import create_app
from app.modules.discovery.config import get_settings
from app.modules.discovery.domain.drafts import draft_from_lead
from app.modules.discovery.domain.leads import DiscoveredLead
from tests.slack_test_helpers import (
    mock_slack_auth,
    mock_slack_ephemeral,
)
from tests.slack_test_helpers import post_interactivity as _shared_post_interactivity

app = create_app()


@pytest.fixture(autouse=True)
def _mock_slack_auth(monkeypatch):
    mock_slack_auth(monkeypatch)


def _post_interactivity(payload: dict):
    return _shared_post_interactivity(app, get_settings().slack_signing_secret, payload)


def _block_action_payload(lead: DiscoveredLead) -> dict:
    return {
        "type": "block_actions",
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
        "trigger_id": "trigger.123",
        "actions": [
            {"action_id": "discover_add_seller", "value": encode_draft(draft_from_lead(lead))}
        ],
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
    posted = mock_slack_ephemeral(monkeypatch)

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
    posted = mock_slack_ephemeral(monkeypatch)

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


def test_discover_review_seller_opens_the_stored_review(monkeypatch) -> None:
    calls: list[dict] = []

    class _FakeService:
        async def open_review_form(self, **kwargs):
            calls.append(kwargs)

    monkeypatch.setattr(handlers_module, "discovery_service", lambda: _FakeService())

    response = _post_interactivity(
        {
            "type": "block_actions",
            "user": {"id": "U_TEST"},
            "channel": {"id": "C_TEST"},
            "trigger_id": "trigger.123",
            "actions": [{"action_id": "discover_review_seller", "value": "place-1"}],
        }
    )

    assert response.status_code == 200
    assert calls == [
        {
            "trigger_id": "trigger.123",
            "review_id": "place-1",
            "channel_id": "C_TEST",
            "requested_by": "U_TEST",
        }
    ]


def test_discover_review_seller_reports_an_unknown_review(monkeypatch) -> None:
    posted = mock_slack_ephemeral(monkeypatch)

    class _MissingService:
        async def open_review_form(self, **_kwargs):
            raise RuntimeError("gone")

    monkeypatch.setattr(handlers_module, "discovery_service", lambda: _MissingService())

    response = _post_interactivity(
        {
            "type": "block_actions",
            "user": {"id": "U_TEST"},
            "channel": {"id": "C_TEST"},
            "trigger_id": "trigger.123",
            "actions": [{"action_id": "discover_review_seller", "value": "place-1"}],
        }
    )

    assert response.status_code == 200
    assert posted[0]["text"] == "Couldn't process that lead."
