"""End-to-end Slack command dispatch through the **merged** app (`main.py`)
— proves the actual thing this merge exists to fix: one process, one
`AsyncApp`, all 5 commands (matching-engine's `/find-match` plus
ddl-commands' `/edit-seller`/`/edit-buyer`/`/add-seller`/`/add-buyer`)
correctly registered and dispatching, with no cross-package collision.

Each package's own test suite (`matching-engine/tests/`, `ddl-commands/tests/`)
already covers its own business logic and Slack wiring in isolation via its
own standalone `app`/`ddl_commands` FastAPI instance — this file only tests
what's new here: the merge itself. Signs requests the way Slack really does
(HMAC-SHA256 over `v0:<timestamp>:<body>`) so Bolt's real signature
verification is exercised, not bypassed. The Slack Web API client is
monkeypatched — no network calls leave the process.
"""

import hashlib
import hmac
import json
import time
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import main
from app.modules.matching_engine.config import get_settings


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


class _FakeAuthTestResponse(dict):
    """Bolt reads both dict-style (`["user_id"]`) and `.headers` off the
    `auth.test` result — a plain dict fails on the latter.
    """

    headers: dict = {}


@pytest.fixture(autouse=True)
def _mock_slack_web_client(monkeypatch):
    posted: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral", fake_chat_post_ephemeral
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)
    return posted


def _post_command(command: str, text: str = "") -> TestClient:
    settings = get_settings()
    body = urlencode(
        {
            "command": command,
            "text": text,
            "channel_id": "C_TEST",
            "user_id": "U_TEST",
            "trigger_id": f"trigger-{command}-{text}",
            "team_id": "T_TEST",
            "response_url": "https://hooks.slack.test/x",
        }
    )
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)
    client = TestClient(main.app)
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )


def _post_view_submission_raw(view: dict) -> TestClient:
    settings = get_settings()
    payload = {"type": "view_submission", "user": {"id": "U_TEST"}, "view": view}
    body = urlencode({"payload": json.dumps(payload)})
    timestamp = str(int(time.time()))
    signature = _sign(body, timestamp, settings.slack_signing_secret)
    client = TestClient(main.app)
    return client.post(
        "/slack/events",
        content=body,
        headers={
            "Content-Type": "application/x-www-form-urlencoded",
            "X-Slack-Request-Timestamp": timestamp,
            "X-Slack-Signature": signature,
        },
    )


@pytest.mark.parametrize(
    "command", ["/find-match", "/edit-seller", "/edit-buyer", "/add-seller", "/add-buyer"]
)
def test_every_command_dispatches_off_the_one_shared_app(
    command: str, _mock_slack_web_client
) -> None:
    """All 5 slash commands route correctly through the single merged
    `AsyncApp` — the empty-text usage-message path touches neither the DB
    nor any business logic, so this is a pure wiring check.
    """
    response = _post_command(command)

    assert response.status_code == 200
    assert len(_mock_slack_web_client) == 1
    assert "Usage" in _mock_slack_web_client[0]["text"]
    assert command in _mock_slack_web_client[0]["text"]


def _view_state_with_selected_buyer(buyer_role_id: str) -> dict:
    """Both matching-engine's and ddl-commands' buyer-selection modals happen
    to use the identical block_id/action_id shape (`buyer_role_id` /
    `selected_buyer`) — coincidental, but means one state payload shape
    drives both of the tests below.
    """
    return {"buyer_role_id": {"selected_buyer": {"selected_option": {"value": buyer_role_id}}}}


def test_buyer_selection_modal_routes_to_matching_engine_not_ddl_commands(monkeypatch) -> None:
    """The exact bug this merge exists to prevent: matching-engine's own
    `buyer_selection_modal` (its `/find-match` match-target disambiguation)
    must fire matching-engine's handler, never ddl-commands' — which is
    exactly why ddl-commands' equivalent callback_id was renamed to
    `buyer_role_selection_modal`.
    """
    from app.modules.ddl_commands.api.slack.handlers import actions as ddl_commands_actions
    from app.modules.matching_engine.api.slack.handlers import (
        actions as matching_engine_actions,
    )

    task_runner_calls: list[tuple] = []
    monkeypatch.setattr(
        matching_engine_actions._task_runner,
        "run",
        lambda fn, name: task_runner_calls.append((fn, name)),
    )

    async def fail_if_called(*_args, **_kwargs):
        raise AssertionError("ddl-commands' resolve_buyer_by_id must not be called")

    monkeypatch.setattr(ddl_commands_actions, "resolve_buyer_by_id", fail_if_called)

    view = {
        "type": "modal",
        "id": "V1",
        "callback_id": "buyer_selection_modal",
        "private_metadata": json.dumps({"requested_by": "U_TEST", "channel_id": "C_TEST"}),
        "state": {"values": _view_state_with_selected_buyer("buyer-role-123")},
    }
    response = _post_view_submission_raw(view)

    assert response.status_code == 200
    assert len(task_runner_calls) == 1


def test_duplicate_buyer_selection_submission_dispatches_once(monkeypatch) -> None:
    from app.modules.matching_engine.api.slack.handlers import (
        actions as matching_engine_actions,
    )

    task_runner_calls: list[tuple] = []
    monkeypatch.setattr(
        matching_engine_actions._task_runner,
        "run",
        lambda fn, name: task_runner_calls.append((fn, name)),
    )
    view = {
        "type": "modal",
        "id": "V_RETRY_DEDUPLICATION",
        "callback_id": "buyer_selection_modal",
        "private_metadata": json.dumps({"requested_by": "U_TEST", "channel_id": "C_TEST"}),
        "state": {"values": _view_state_with_selected_buyer("buyer-role-retry")},
    }

    first = _post_view_submission_raw(view)
    second = _post_view_submission_raw(view)

    assert first.status_code == 200
    assert second.status_code == 200
    assert len(task_runner_calls) == 1


def test_buyer_role_selection_modal_routes_to_ddl_commands_not_matching_engine(monkeypatch) -> None:
    """The ddl-commands side of the same fix: `/edit-buyer`'s disambiguation
    modal must fire ddl-commands' handler, never matching-engine's.
    """
    from app.modules.matching_engine.api.slack.handlers import (
        actions as matching_engine_actions,
    )

    def fail_if_called(*_args, **_kwargs):
        raise AssertionError("matching-engine's task runner must not be called")

    monkeypatch.setattr(matching_engine_actions._task_runner, "run", fail_if_called)

    view = {
        "type": "modal",
        "id": "V1",
        "callback_id": "buyer_role_selection_modal",
        "private_metadata": json.dumps(
            {
                "requested_by": "U_TEST",
                "channel_id": "C_TEST",
                "org_names": {"buyer-role-123": "Blue Horizon Buyers"},
            }
        ),
        "state": {"values": _view_state_with_selected_buyer("buyer-role-123")},
    }
    response = _post_view_submission_raw(view)

    assert response.status_code == 200
    # ddl-commands' handler is the only one that answers this callback_id with
    # the buyer field picker — that response *is* the proof of routing. It used
    # to be proven by spying on a database call, but that call was removed: the
    # handler has 3s to ack and no longer queries before doing so.
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "buyer_field_picker_modal"
