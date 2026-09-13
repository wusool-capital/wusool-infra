"""Slack command -> acknowledgement -> usage-message dispatch, without an
actual Slack workspace. Signs the request the way Slack really does
(HMAC-SHA256 over `v0:<timestamp>:<body>`) so Bolt's real signature
verification is exercised, not bypassed. The Slack Web API client is
monkeypatched — no network calls leave the process. Mirrors matching-engine's
`test_slack_command_dispatch.py` pattern exactly.
"""

import pytest

from app.modules.ddl_commands.bootstrap import create_app
from app.modules.ddl_commands.config import get_settings
from tests.slack_test_helpers import mock_slack_auth, mock_slack_ephemeral, post_slack_command

app = create_app()


@pytest.mark.parametrize("command", ["/edit-seller", "/edit-buyer", "/add-seller", "/add-buyer"])
def test_command_with_no_text_posts_usage_without_touching_db(command: str, monkeypatch) -> None:
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)

    settings = get_settings()
    response = post_slack_command(app, settings.slack_signing_secret, command=command, text="")

    assert response.status_code == 200
    assert len(posted) == 1
    assert "Usage" in posted[0]["text"]
