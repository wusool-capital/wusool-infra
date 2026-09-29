"""`/check-buyer` dispatch through this module's own standalone app.
Mirrors `enrichment.tests.integration.test_slack_command_dispatch`.
"""

from app.modules.discrepancies.api.slack.handlers import commands as commands_module
from app.modules.discrepancies.bootstrap import create_app
from app.modules.discrepancies.config import get_settings
from app.modules.discrepancies.domain.criteria import BuyerCriteria
from tests.slack_test_helpers import mock_slack_auth, mock_slack_ephemeral, post_slack_command

app = create_app()


def test_check_buyer_with_empty_text_shows_usage(monkeypatch) -> None:
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)

    response = post_slack_command(
        app, get_settings().slack_signing_secret, command="/check-buyer", text=""
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "Usage" in posted[0]["text"]
    assert "/check-buyer" in posted[0]["text"]


def test_check_buyer_with_no_match_shows_notice(monkeypatch) -> None:
    mock_slack_auth(monkeypatch)
    updated: list[dict] = []

    async def fake_views_open(self, **kwargs):
        return {"view": {"id": "V_TEST"}}

    async def fake_views_update(self, **kwargs):
        updated.append(kwargs)
        return {"ok": True}

    async def fake_search_buyers(name: str) -> list[BuyerCriteria]:
        return []

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_open", fake_views_open)
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_update", fake_views_update)
    monkeypatch.setattr(commands_module, "search_buyers", fake_search_buyers)

    response = post_slack_command(
        app,
        get_settings().slack_signing_secret,
        command="/check-buyer",
        text="Nonexistent Capital",
        trigger_id="trigger.no-match",
    )

    assert response.status_code == 200
    assert len(updated) == 1
    assert "No buyer found" in str(updated[0]["view"].blocks[0].text.text)


def test_check_buyer_with_one_match_shows_picker(monkeypatch) -> None:
    mock_slack_auth(monkeypatch)
    updated: list[dict] = []

    async def fake_views_open(self, **kwargs):
        return {"view": {"id": "V_TEST"}}

    async def fake_views_update(self, **kwargs):
        updated.append(kwargs)
        return {"ok": True}

    async def fake_search_buyers(name: str) -> list[BuyerCriteria]:
        return [
            BuyerCriteria(
                buyer_role_id="role-1", org_name="Shahroukh Capital", target_vertical="Pharma"
            )
        ]

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_open", fake_views_open)
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_update", fake_views_update)
    monkeypatch.setattr(commands_module, "search_buyers", fake_search_buyers)

    response = post_slack_command(
        app,
        get_settings().slack_signing_secret,
        command="/check-buyer",
        text="Shahroukh",
        trigger_id="trigger.one-match",
    )

    assert response.status_code == 200
    assert len(updated) == 1
    assert updated[0]["view"].callback_id == "discrepancy_buyer_picker_modal"
