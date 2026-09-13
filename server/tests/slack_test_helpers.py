"""Shared plumbing for every module's Slack integration tests: signing a
request the way Slack really does (HMAC-SHA256 over `v0:<timestamp>:<body>`)
so Bolt's own signature verification is exercised rather than bypassed, and
faking the two Slack Web API calls Bolt itself makes that every such test
must keep off the network — `auth.test` (called once per process on first
dispatch, to verify/cache the bot's identity) and `chat.postEphemeral`
(this codebase's standard way of telling an operator something went wrong).

Previously near-identical private copies in 7 files across `ddl_commands`,
`discovery`, `enrichment`, `matching_engine`, and this directory's own
`test_merged_command_dispatch.py` — sharing test-tree code carries none of
production code's cross-module import restrictions (see
`test_architecture.py`'s own `_module_source_files`, which excludes any
path with `tests` in it; `test_enrichment_field_vocabulary.py` already
relies on the same fact).

Every module builds its own `app` from its own `bootstrap.create_app()` (or
`main.app` for the merged app), so nothing here holds one — every function
takes it as a parameter.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

from fastapi.testclient import TestClient
from starlette.testclient import TestClient as StarletteTestClient


def sign_slack_request(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def post_signed_slack_request(app, body: str, signing_secret: str) -> StarletteTestClient:
    timestamp = str(int(time.time()))
    signature = sign_slack_request(body, timestamp, signing_secret)
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


def post_slack_command(
    app,
    signing_secret: str,
    *,
    command: str,
    text: str = "",
    channel_id: str = "C_TEST",
    user_id: str = "U_TEST",
    trigger_id: str = "trigger.123",
    **extra_fields: str,
) -> StarletteTestClient:
    body = urlencode(
        {
            "command": command,
            "text": text,
            "channel_id": channel_id,
            "user_id": user_id,
            "trigger_id": trigger_id,
            **extra_fields,
        }
    )
    return post_signed_slack_request(app, body, signing_secret)


def post_interactivity(app, signing_secret: str, payload: dict) -> StarletteTestClient:
    body = urlencode({"payload": json.dumps(payload)})
    return post_signed_slack_request(app, body, signing_secret)


class FakeAuthTestResponse(dict):
    """Bolt reads both dict-style (`["user_id"]`) and `.headers` off the
    `auth.test` result — a plain dict fails on the latter.
    """

    headers: dict = {}


def mock_slack_auth(monkeypatch) -> None:
    """Bolt calls `auth.test` on its first dispatch to verify/cache the
    bot's identity — a real network call every test in this file must not
    make.
    """

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)


def mock_slack_ephemeral(monkeypatch) -> list[dict]:
    """Returns the list `chat.postEphemeral` calls accumulate into — assert
    against it after the request completes.
    """
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral", fake_chat_post_ephemeral
    )
    return posted
