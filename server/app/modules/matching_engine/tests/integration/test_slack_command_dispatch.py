"""§33: Slack command -> acknowledgement -> application use-case invocation,
without an actual Slack workspace. Signs the request the way Slack really
does (HMAC-SHA256 over `v0:<timestamp>:<body>`) so Bolt's real signature
verification (§2, §37) is exercised, not bypassed. The Slack Web API client
is monkeypatched — no network calls leave the process.
"""

from app.modules.matching_engine.bootstrap import create_app
from app.modules.matching_engine.config import get_settings
from tests.slack_test_helpers import mock_slack_auth, mock_slack_ephemeral, post_slack_command

app = create_app()


def test_find_match_with_no_text_posts_usage_without_touching_bedrock_or_db(monkeypatch) -> None:
    posted = mock_slack_ephemeral(monkeypatch)
    mock_slack_auth(monkeypatch)

    settings = get_settings()
    response = post_slack_command(app, settings.slack_signing_secret, command="/find-match")

    assert response.status_code == 200
    assert len(posted) == 1
    assert "Usage" in posted[0]["text"]
