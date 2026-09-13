"""Slack command -> acknowledgement -> usage-message dispatch, without an
actual Slack workspace. Signs the request the way Slack really does
(HMAC-SHA256 over `v0:<timestamp>:<body>`) so Bolt's real signature
verification is exercised, not bypassed. The Slack Web API client is
monkeypatched — no network calls leave the process. Mirrors
`ddl_commands`'/`matching_engine`'s own `test_slack_command_dispatch.py`.
"""

from app.modules.enrichment.api.slack.handlers import commands as commands_module
from app.modules.enrichment.bootstrap import create_app
from app.modules.enrichment.config import get_settings
from app.modules.enrichment.domain.targets import ResolvedOrgRole
from tests.slack_test_helpers import mock_slack_auth, mock_slack_ephemeral, post_slack_command

app = create_app()


def test_enrich_seller_with_no_text_posts_seller_scoped_usage(monkeypatch) -> None:
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)

    settings = get_settings()
    response = post_slack_command(
        app,
        settings.slack_signing_secret,
        command="/enrich-seller",
        text="",
        trigger_id="trigger.123",
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "/enrich-seller <seller name>" in posted[0]["text"]


def test_enrich_seller_ignores_a_buyer_only_match(monkeypatch) -> None:
    """An org with only a buyer role must not be treated as a candidate for
    `/enrich-seller` — the kind filter should leave zero candidates, not
    silently fall through to enriching the buyer role.
    """
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)
    updated: list[dict] = []

    async def fake_resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
        return [
            ResolvedOrgRole(
                org_attio_id="org-1", org_name="Blue Horizon", role_id="role-1", kind="buyer"
            )
        ]

    async def fake_views_open(self, **kwargs):  # noqa: ANN001
        return {"view": {"id": "V_TEST"}}

    async def fake_views_update(self, **kwargs):  # noqa: ANN001
        updated.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_open", fake_views_open)
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_update", fake_views_update)
    monkeypatch.setattr(commands_module, "resolve_org_roles", fake_resolve_org_roles)

    settings = get_settings()
    response = post_slack_command(
        app,
        settings.slack_signing_secret,
        command="/enrich-seller",
        text="Blue Horizon",
        trigger_id="trigger.456",
    )

    assert response.status_code == 200
    # The message moved into the modal the command already opened; an ephemeral
    # would mean it fell through to the error path in `_run`.
    assert posted == []
    assert len(updated) == 1
    assert "No active seller found for *Blue Horizon*" in str(
        updated[0]["view"].blocks[0].text.text
    )


def test_enrich_buyer_with_no_text_posts_buyer_scoped_usage(monkeypatch) -> None:
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)

    settings = get_settings()
    response = post_slack_command(
        app,
        settings.slack_signing_secret,
        command="/enrich-buyer",
        text="",
        trigger_id="trigger.789",
    )

    assert response.status_code == 200
    assert len(posted) == 1
    assert "/enrich-buyer <buyer name>" in posted[0]["text"]


def test_enrich_buyer_ignores_a_seller_only_match(monkeypatch) -> None:
    """Mirror of `test_enrich_seller_ignores_a_buyer_only_match` — an org
    with only a seller role must not be treated as a candidate for
    `/enrich-buyer`.
    """
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)
    updated: list[dict] = []

    async def fake_resolve_org_roles(org_name: str) -> list[ResolvedOrgRole]:
        return [
            ResolvedOrgRole(
                org_attio_id="org-2", org_name="Acme Rollup", role_id="role-2", kind="seller"
            )
        ]

    async def fake_views_open(self, **kwargs):  # noqa: ANN001
        return {"view": {"id": "V_TEST"}}

    async def fake_views_update(self, **kwargs):  # noqa: ANN001
        updated.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_open", fake_views_open)
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.views_update", fake_views_update)
    monkeypatch.setattr(commands_module, "resolve_org_roles", fake_resolve_org_roles)

    settings = get_settings()
    response = post_slack_command(
        app,
        settings.slack_signing_secret,
        command="/enrich-buyer",
        text="Acme Rollup",
        trigger_id="trigger.101",
    )

    assert response.status_code == 200
    # The message moved into the modal the command already opened; an ephemeral
    # would mean it fell through to the error path in `_run`.
    assert posted == []
    assert len(updated) == 1
    assert "No active buyer found for *Acme Rollup*" in str(updated[0]["view"].blocks[0].text.text)
