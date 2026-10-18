"""A number Slack would reject must never stop a form opening, on any path."""

import json
import time
from typing import Any
from unittest.mock import AsyncMock, patch
from urllib.parse import urlencode

import pytest
from slack_bolt.async_app import AsyncApp, AsyncBoltRequest
from slack_bolt.context.ack.async_ack import AsyncAck
from slack_sdk.errors import SlackApiError
from slack_sdk.signature import SignatureVerifier
from slack_sdk.web.async_client import AsyncWebClient
from slack_sdk.web.async_slack_response import AsyncSlackResponse

from app.modules.notifications.providers.slack.bolt_app import GuardedAck, build_bolt_app
from app.modules.notifications.providers.slack.client import NoUnfurlWebClient, guard_view


def _view(value: str, *, is_decimal_allowed: bool) -> dict[str, Any]:
    element = {
        "type": "number_input",
        "action_id": "n",
        "is_decimal_allowed": is_decimal_allowed,
        "initial_value": value,
    }
    return {"type": "modal", "blocks": [{"type": "input", "block_id": "n", "element": element}]}


def _initial(view: dict[str, Any]) -> str | None:
    return view["blocks"][0]["element"].get("initial_value")


@pytest.mark.parametrize(
    ("value", "is_decimal_allowed"),
    [("12.0", False), ("1.5e+16", True), ("1.5e+16", False), ("nan", True), ("inf", True)],
)
def test_invalid_number_is_blanked(value: str, is_decimal_allowed: bool) -> None:
    view = _view(value, is_decimal_allowed=is_decimal_allowed)

    assert _initial(guard_view(view)) is None
    assert _initial(view) == value  # caller's view is not mutated


@pytest.mark.parametrize(
    ("value", "is_decimal_allowed"), [("12", False), ("-3", False), ("12.5", True), ("12", True)]
)
def test_valid_number_is_kept(value: str, is_decimal_allowed: bool) -> None:
    assert _initial(guard_view(_view(value, is_decimal_allowed=is_decimal_allowed))) == value


@pytest.mark.parametrize("method", ["views.open", "views.update", "views.push"])
async def test_client_guards_every_view_call(method: str) -> None:
    with patch.object(AsyncWebClient, "api_call", new_callable=AsyncMock) as base:
        await NoUnfurlWebClient(token="x").api_call(
            method, json={"view": _view("12.0", is_decimal_allowed=False)}
        )

    assert _initial(base.call_args.kwargs["json"]["view"]) is None


async def test_client_logs_slacks_reason_when_a_view_is_rejected(
    caplog: pytest.LogCaptureFixture,
) -> None:
    response = {"ok": False, "response_metadata": {"messages": ["[ERROR] bad /blocks/3"]}}
    error = SlackApiError("invalid_arguments", response)
    with (
        patch.object(AsyncWebClient, "api_call", new_callable=AsyncMock, side_effect=error),
        pytest.raises(SlackApiError),
    ):
        await NoUnfurlWebClient(token="x").api_call("views.open", json={"view": {}})

    assert "bad /blocks/3" in caplog.text


async def test_guarded_ack_guards_response_action_view() -> None:
    ack = GuardedAck()
    await ack(response_action="update", view=_view("12.0", is_decimal_allowed=False))

    assert ack.response is not None
    assert _initial(json.loads(ack.response.body)["view"]) is None


async def test_every_bolt_app_acks_through_the_guard() -> None:
    seen: list[AsyncAck] = []

    def register(app: AsyncApp) -> None:
        @app.view("form")
        async def handle(ack: AsyncAck) -> None:
            seen.append(ack)
            await ack(response_action="update", view=_view("12.0", is_decimal_allowed=False))

    app = build_bolt_app("xoxb-test", "secret", register)
    payload = {"type": "view_submission", "team": {"id": "T1"}, "user": {"id": "U1"}}
    payload["view"] = {"id": "V1", "type": "modal", "callback_id": "form", "state": {"values": {}}}
    body = urlencode({"payload": json.dumps(payload)})
    timestamp = str(int(time.time()))
    signature = SignatureVerifier("secret").generate_signature(timestamp=timestamp, body=body)
    headers = {
        "content-type": ["application/x-www-form-urlencoded"],
        "x-slack-request-timestamp": [timestamp],
        "x-slack-signature": [signature],
    }
    auth = AsyncSlackResponse(
        client=None,
        http_verb="POST",
        api_url="auth.test",
        req_args={},
        data={"ok": True, "user_id": "UB", "bot_id": "B1", "team_id": "T1"},
        headers={},
        status_code=200,
    )
    with patch.object(AsyncWebClient, "api_call", new_callable=AsyncMock, return_value=auth):
        response = await app.async_dispatch(AsyncBoltRequest(body=body, headers=headers))

    assert isinstance(seen[0], GuardedAck)
    assert _initial(json.loads(response.body)["view"]) is None
