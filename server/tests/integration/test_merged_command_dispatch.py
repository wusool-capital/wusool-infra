"""End-to-end Slack command dispatch through the **merged** app (`main.py`)
— proves the actual thing this merge exists to fix: one process, one
`AsyncApp`, all 9 commands (matching-engine's `/find-match`,
ddl-commands' `/edit-seller`/`/edit-buyer`/`/add-seller`/`/add-buyer`,
enrichment's `/enrich-seller`/`/enrich-buyer`, and `main.py`'s own
`/help`/`/status`) correctly registered and dispatching, with no
cross-package collision.

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
from app.modules.lead_magnets.api import dependencies as lead_magnet_deps
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
    "command",
    [
        "/find-match",
        "/edit-seller",
        "/edit-buyer",
        "/add-seller",
        "/add-buyer",
        "/enrich-seller",
        "/enrich-buyer",
    ],
)
def test_every_command_dispatches_off_the_one_shared_app(
    command: str, _mock_slack_web_client
) -> None:
    """Every slash command but `/help` routes correctly through the single
    merged `AsyncApp` — the empty-text usage-message path touches neither
    the DB nor any business logic, so this is a pure wiring check. `/help`
    has no usage message (it always answers the same way regardless of
    text) — covered separately below.
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


def test_help_command_lists_every_command(_mock_slack_web_client) -> None:
    """`/help` isn't owned by any one module — `main.py`'s own
    `_COMMAND_HELP` list is the single source of truth, so this pins that
    every command actually registered on the app also appears in the help
    text (catching the same class of staleness `SLACK_APP_SETUP.md` had
    before it was updated to match).
    """
    response = _post_command("/help")

    assert response.status_code == 200
    assert len(_mock_slack_web_client) == 1
    text = _mock_slack_web_client[0]["text"]
    for command, _hint, _description in main._COMMAND_HELP:
        assert f"`{command}" in text


def test_command_help_and_service_map_stay_in_sync() -> None:
    """`_SERVICE_BY_TRIGGER` (dispatch logging) and `_COMMAND_HELP` (`/help`'s
    own text) are two independently hand-maintained lists of the same
    command set — nothing else catches one going stale relative to the
    other, so this does.
    """
    help_commands = {command for command, _hint, _description in main._COMMAND_HELP}
    assert help_commands == set(main._SERVICE_BY_TRIGGER)


def test_status_command_reports_healthy_database(monkeypatch, _mock_slack_web_client) -> None:
    async def fake_check_database_connectivity() -> None:
        return None

    monkeypatch.setattr(main, "check_database_connectivity", fake_check_database_connectivity)
    monkeypatch.setattr(main, "attio_is_test", lambda: True)

    response = _post_command("/status")

    assert response.status_code == 200
    text = _mock_slack_web_client[0]["text"]
    assert "Database: reachable" in text
    assert "Attio: test" in text


def test_status_command_reports_unreachable_database(monkeypatch, _mock_slack_web_client) -> None:
    async def fake_check_database_connectivity() -> None:
        raise ConnectionError("no route to host")

    monkeypatch.setattr(main, "check_database_connectivity", fake_check_database_connectivity)
    monkeypatch.setattr(main, "attio_is_test", lambda: False)

    response = _post_command("/status")

    assert response.status_code == 200
    text = _mock_slack_web_client[0]["text"]
    assert "Database: unreachable" in text
    assert "Attio: production" in text


def test_lead_magnet_static_mount_does_not_shadow_existing_routes() -> None:
    """The static mount (`app.mount("/", ToolStatic(...))`) is the newest
    thing merged into this app, registered last — the same collision risk
    this file already exists to catch for the Slack handlers. Proven live
    once: `GET /readiness` is a k8s-style DB-connectivity probe unrelated
    to the readiness *tool*, which will eventually serve at `/readiness/`
    (trailing slash) — exact-path route registration keeps them apart.
    """
    client = TestClient(main.app)

    # `rate_limit`'s counter is a module-level singleton shared by every
    # test in this process, keyed on TestClient's fixed "testclient" host —
    # by the time this file's tests run, lead_magnets' own integration
    # suite has already spent some of the hourly quota against that same
    # key. Reset it so the three POSTs below are judged on their own,
    # exactly as `test_api_guards.py` already does for its own assertions
    # about this limiter.
    lead_magnet_deps._limiter = None

    assert client.get("/health").status_code == 200
    # 503 here means "no real database in this test", not "route missing" —
    # the k8s probe still answered, which is what this test checks.
    assert client.get("/readiness").status_code in (200, 503)
    assert client.get("/ready").status_code in (200, 503)

    assert client.get("/embed.js").status_code == 200
    assert client.get("/benchmark/", follow_redirects=False).status_code == 200
    assert client.get("/readiness/", follow_redirects=False).status_code == 200
    assert client.get("/valuation/", follow_redirects=False).status_code == 200
    assert client.get("/buyers/", follow_redirects=False).status_code == 200
    assert client.get("/img/5ba450cc.png").status_code == 200
    assert client.get("/img/a0288d00.png").status_code == 200
    assert client.get("/shared/height.js").status_code == 200
    assert client.get("/valuation/10-data.js").status_code == 200
    assert client.get("/buyers/10-main.js").status_code == 200

    # POST /benchmark is the real submission API, at the same path prefix
    # as the GET-only static page — different HTTP methods, no collision.
    response = client.post("/benchmark", json={})
    assert response.status_code == 422  # reaches request validation, not a 404

    # /readiness/score is the real submission API for the readiness tool —
    # a sibling path to the GET-only /readiness/ static page, not a
    # collision.
    response = client.post("/readiness/score", json={})
    assert response.status_code == 422

    # /buyer/apply (singular) is the real submission API; /buyers/
    # (plural) is the static page — different path prefixes entirely, so
    # this one was never even a near-collision like the other three.
    response = client.post("/buyer/apply", json={})
    assert response.status_code == 422

    assert client.get("/this-path-does-not-exist/").status_code == 404
