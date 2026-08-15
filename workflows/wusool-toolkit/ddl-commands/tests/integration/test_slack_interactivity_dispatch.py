"""End-to-end Slack *interactivity* dispatch — closes the gap between "the
repository/use-case logic is correct" (proven against a real Postgres in
`test_seller_use_cases.py`/`test_buyer_use_cases.py`) and "the wiring from a
real Slack payload to that logic is correct." No live Slack workspace, no
database: every payload is hand-built to match Slack's real `view_submission`/
`block_actions` shape, signed with the same HMAC scheme Slack really uses
(exercising Bolt's real signature verification, same as
`test_slack_command_dispatch.py`), and every DB-touching call
(`resolve_*_by_id`, `count_match_results_for_*`, the write use cases) is
monkeypatched at its import site in `app.modules.slack.handlers.actions` so
this file asserts *the right function got called with the right arguments*,
not the real DB side effect.
"""

import hashlib
import hmac
import json
import time
import uuid
from types import SimpleNamespace
from urllib.parse import urlencode

import pytest
from fastapi.testclient import TestClient

import app.modules.slack.handlers.actions as actions_module
from app.config import get_settings
from app.main import app


def _sign(body: str, timestamp: str, signing_secret: str) -> str:
    basestring = f"v0:{timestamp}:{body}".encode()
    digest = hmac.new(signing_secret.encode(), basestring, hashlib.sha256).hexdigest()
    return f"v0={digest}"


def _post_interactivity(payload: dict) -> "TestClient.__class__":
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


def _async_returning(value):
    """`resolve_*_by_id`/`count_match_results_for_*` are `await`ed at their
    call site — a plain lambda returning a value isn't awaitable, so every
    monkeypatch of one of those needs an actual coroutine function.
    """

    async def _fn(*_args, **_kwargs):
        return value

    return _fn


def _fake_org(name: str = "Acme Capital"):
    return SimpleNamespace(name=name)


def _fake_seller_role(role_id: str, *, removed: bool = False, org_name: str = "Acme Capital"):
    return SimpleNamespace(
        id=role_id,
        organization=_fake_org(org_name),
        removed_at="2026-01-01T00:00:00Z" if removed else None,
        outreach_tier=None,
        appetite_signal=None,
        relationship_status=None,
        est_revenue=None,
        est_ebitda=None,
        owner_salary=None,
        valuation_low=None,
        valuation_mid=None,
        valuation_high=None,
        sell_timeline=None,
        readiness_score=None,
        readiness_band=None,
        intake_source=None,
        last_attempt_date=None,
        last_attempt_channel=None,
        last_attempt_outcome=None,
        lead_quality_score=None,
        re_engage_date=None,
    )


def _fake_buyer_role(role_id: str, *, removed: bool = False, org_name: str = "Blue Horizon"):
    return SimpleNamespace(
        id=role_id,
        organization=_fake_org(org_name),
        removed_at="2026-01-01T00:00:00Z" if removed else None,
        model=None,
        mandate_status=None,
        ebitda_floor=None,
        check_size_min=None,
        check_size_max=None,
        ev_ceiling=None,
        deal_structure_tolerance=None,
        earnout_tolerance=None,
        profitable_only=None,
        investment_strategy=None,
        notes=None,
        acquisition_enrichment=None,
        deals_introduced=None,
        deals_converted=None,
    )


class _RecordingUseCase:
    def __init__(self, result=None, raises=None):
        self.calls: list[tuple[tuple, dict]] = []
        self._result = result
        self._raises = raises

    async def execute(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self._raises is not None:
            raise self._raises
        return self._result


@pytest.fixture(autouse=True)
def _mock_slack_web_client(monkeypatch):
    posted: list[dict] = []
    responded: list[dict] = []

    async def fake_chat_post_ephemeral(self, **kwargs):  # noqa: ANN001
        posted.append(kwargs)
        return {"ok": True}

    class _FakeAuthTestResponse(dict):
        headers: dict = {}

    async def fake_auth_test(self, **kwargs):  # noqa: ANN001
        return _FakeAuthTestResponse(ok=True, user_id="U_BOT", team_id="T_TEST", bot_id="B_TEST")

    async def fake_send_dict(self, message, **kwargs):  # noqa: ANN001
        responded.append(message)

        class _FakeWebhookResponse:
            status_code = 200
            body = "ok"

        return _FakeWebhookResponse()

    monkeypatch.setattr(
        "slack_sdk.web.async_client.AsyncWebClient.chat_postEphemeral", fake_chat_post_ephemeral
    )
    monkeypatch.setattr("slack_sdk.web.async_client.AsyncWebClient.auth_test", fake_auth_test)
    monkeypatch.setattr(
        "slack_sdk.webhook.async_client.AsyncWebhookClient.send_dict", fake_send_dict
    )
    return SimpleNamespace(posted=posted, responded=responded)


# --------------------------------------------------------------------------
# seller_selection_modal submission
# --------------------------------------------------------------------------


def test_seller_selection_edit_intent_opens_prefilled_edit_form(monkeypatch) -> None:
    seller_id = str(uuid.uuid4())
    monkeypatch.setattr(
        actions_module,
        "resolve_seller_by_id",
        _async_returning(_fake_seller_role(seller_id, org_name="Typo Target Co")),
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V1",
            "callback_id": "seller_selection_modal",
            "private_metadata": json.dumps(
                {"requested_by": "U_TEST", "channel_id": "C_TEST", "intent": "edit"}
            ),
            "state": {
                "values": {
                    "seller_role_id": {
                        "selected_seller": {"selected_option": {"value": seller_id}}
                    }
                }
            },
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    assert body["view"]["callback_id"] == "seller_edit_form_modal"
    metadata = json.loads(body["view"]["private_metadata"])
    assert metadata["seller_role_id"] == seller_id
    assert metadata["org_name"] == "Typo Target Co"
    assert metadata["removed"] is False


def test_seller_selection_remove_intent_posts_confirmation_with_match_count(
    monkeypatch, _mock_slack_web_client
) -> None:
    seller_id = str(uuid.uuid4())
    monkeypatch.setattr(
        actions_module, "resolve_seller_by_id", _async_returning(_fake_seller_role(seller_id))
    )
    monkeypatch.setattr(
        actions_module, "count_match_results_for_seller", _async_returning(3)
    )

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V1",
            "callback_id": "seller_selection_modal",
            "private_metadata": json.dumps(
                {"requested_by": "U_TEST", "channel_id": "C_TEST", "intent": "remove"}
            ),
            "state": {
                "values": {
                    "seller_role_id": {
                        "selected_seller": {"selected_option": {"value": seller_id}}
                    }
                }
            },
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert len(_mock_slack_web_client.posted) == 1
    posted = _mock_slack_web_client.posted[0]
    assert "3 match record" in json.dumps(posted["blocks"])
    action_blocks = [b for b in posted["blocks"] if b["type"] == "actions"]
    elements = [el for block in action_blocks for el in block["elements"]]
    assert {el["action_id"] for el in elements} == {"remove_seller", "cancel_seller"}
    assert {el["value"] for el in elements} == {seller_id}


# --------------------------------------------------------------------------
# seller_edit_form_modal submission
# --------------------------------------------------------------------------


def _edit_form_payload(
    seller_id: str, *, removed: bool, values: dict, checkbox_checked: bool = False
) -> dict:
    state_values = dict(values)
    if removed:
        state_values["restore_confirmation"] = {
            "confirm_restore": {
                "selected_options": (
                    [{"value": "confirm"}] if checkbox_checked else []
                )
            }
        }
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V2",
            "callback_id": "seller_edit_form_modal",
            "private_metadata": json.dumps(
                {
                    "seller_role_id": seller_id,
                    "org_name": "Acme Capital",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                    "removed": removed,
                }
            ),
            "state": {"values": state_values},
        },
    }


def test_edit_form_invalid_currency_returns_field_error() -> None:
    seller_id = str(uuid.uuid4())
    values = {
        "outreach_tier": {"outreach_tier": {"value": None}},
        "appetite_signal": {"appetite_signal": {"value": None}},
        "relationship_status": {"relationship_status": {"value": None}},
        "est_revenue_amount": {"est_revenue_amount": {"value": "100"}},
        "est_revenue_currency": {"est_revenue_currency": {"value": "usd"}},  # lowercase, invalid
    }
    payload = _edit_form_payload(seller_id, removed=False, values=values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "errors"
    assert "est_revenue_currency" in body["errors"]


def test_edit_form_valid_input_calls_update_use_case_with_extracted_fields(
    monkeypatch, _mock_slack_web_client
) -> None:
    seller_id = str(uuid.uuid4())
    fake_use_case = _RecordingUseCase()
    monkeypatch.setattr(
        actions_module, "build_update_seller_use_case", lambda: fake_use_case
    )

    values = {
        "outreach_tier": {"outreach_tier": {"value": "warm"}},
        "appetite_signal": {"appetite_signal": {"value": None}},
        "relationship_status": {"relationship_status": {"value": None}},
    }
    payload = _edit_form_payload(seller_id, removed=False, values=values)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert response.text == ""  # plain ack(), no response_action
    assert len(fake_use_case.calls) == 1
    args, kwargs = fake_use_case.calls[0]
    assert args[0] == seller_id
    assert args[1]["outreach_tier"] == "warm"
    assert args[2] == "U_TEST"
    assert kwargs["restore"] is False
    assert "Updated seller profile for Acme Capital" in _mock_slack_web_client.posted[0]["text"]


def test_edit_form_removed_target_without_checkbox_requires_confirmation() -> None:
    seller_id = str(uuid.uuid4())
    values = {"outreach_tier": {"outreach_tier": {"value": "warm"}}}
    payload = _edit_form_payload(seller_id, removed=True, values=values, checkbox_checked=False)

    response = _post_interactivity(payload)

    body = response.json()
    assert body["response_action"] == "errors"
    assert "restore_confirmation" in body["errors"]


def test_edit_form_removed_target_with_checkbox_calls_update_with_restore_true(
    monkeypatch, _mock_slack_web_client
) -> None:
    seller_id = str(uuid.uuid4())
    fake_use_case = _RecordingUseCase()
    monkeypatch.setattr(
        actions_module, "build_update_seller_use_case", lambda: fake_use_case
    )

    values = {"outreach_tier": {"outreach_tier": {"value": "warm"}}}
    payload = _edit_form_payload(seller_id, removed=True, values=values, checkbox_checked=True)

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert len(fake_use_case.calls) == 1
    _, kwargs = fake_use_case.calls[0]
    assert kwargs["restore"] is True
    assert "Restored and updated" in _mock_slack_web_client.posted[0]["text"]


# --------------------------------------------------------------------------
# archive/cancel button actions
# --------------------------------------------------------------------------


def _block_action_payload(action_id: str, value: str) -> dict:
    return {
        "type": "block_actions",
        "user": {"id": "U_TEST"},
        "channel": {"id": "C_TEST"},
        "response_url": "https://hooks.slack.com/actions/T_TEST/123/fake",
        "actions": [{"action_id": action_id, "value": value, "type": "button"}],
    }


def test_remove_seller_button_calls_remove_use_case_and_replaces_message(
    monkeypatch, _mock_slack_web_client
) -> None:
    seller_id = str(uuid.uuid4())
    fake_use_case = _RecordingUseCase()
    monkeypatch.setattr(
        actions_module, "build_remove_seller_use_case", lambda: fake_use_case
    )

    response = _post_interactivity(_block_action_payload("remove_seller", seller_id))

    assert response.status_code == 200
    assert len(fake_use_case.calls) == 1
    args, _ = fake_use_case.calls[0]
    assert args == (seller_id, "U_TEST")
    assert "Removed by" in _mock_slack_web_client.posted[0]["text"]
    assert len(_mock_slack_web_client.responded) == 1
    assert "Removed by" in _mock_slack_web_client.responded[0]["text"]
    assert _mock_slack_web_client.responded[0]["replace_original"] is True


def test_remove_seller_button_already_removed_posts_friendly_error(
    monkeypatch, _mock_slack_web_client
) -> None:
    from app.modules.sellers.application.use_cases import SellerAlreadyRemovedError

    seller_id = str(uuid.uuid4())
    fake_use_case = _RecordingUseCase(raises=SellerAlreadyRemovedError(seller_id))
    monkeypatch.setattr(
        actions_module, "build_remove_seller_use_case", lambda: fake_use_case
    )

    response = _post_interactivity(_block_action_payload("remove_seller", seller_id))

    assert response.status_code == 200
    assert "already been removed" in _mock_slack_web_client.posted[0]["text"]
    assert len(_mock_slack_web_client.responded) == 0


def test_cancel_seller_button_replaces_message_with_cancelled(
    monkeypatch, _mock_slack_web_client
) -> None:
    seller_id = str(uuid.uuid4())

    response = _post_interactivity(_block_action_payload("cancel_seller", seller_id))

    assert response.status_code == 200
    assert len(_mock_slack_web_client.responded) == 1
    assert _mock_slack_web_client.responded[0]["text"] == "Cancelled."


# --------------------------------------------------------------------------
# buyer symmetry smoke tests — same wiring, prove it isn't seller-only
# --------------------------------------------------------------------------


def test_buyer_edit_form_valid_input_calls_update_use_case(
    monkeypatch, _mock_slack_web_client
) -> None:
    buyer_id = str(uuid.uuid4())
    fake_use_case = _RecordingUseCase()
    monkeypatch.setattr(actions_module, "build_update_buyer_use_case", lambda: fake_use_case)

    payload = {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": "V3",
            "callback_id": "buyer_edit_form_modal",
            "private_metadata": json.dumps(
                {
                    "buyer_role_id": buyer_id,
                    "org_name": "Blue Horizon",
                    "requested_by": "U_TEST",
                    "channel_id": "C_TEST",
                    "removed": False,
                }
            ),
            "state": {"values": {"model": {"model": {"value": "Roll-up"}}}},
        },
    }

    response = _post_interactivity(payload)

    assert response.status_code == 200
    assert len(fake_use_case.calls) == 1
    args, kwargs = fake_use_case.calls[0]
    assert args[0] == buyer_id
    assert args[1]["model"] == "Roll-up"
    assert kwargs["restore"] is False
    assert "Updated buyer profile for Blue Horizon" in _mock_slack_web_client.posted[0]["text"]


def test_remove_buyer_button_calls_remove_use_case(monkeypatch, _mock_slack_web_client) -> None:
    buyer_id = str(uuid.uuid4())
    fake_use_case = _RecordingUseCase()
    monkeypatch.setattr(actions_module, "build_remove_buyer_use_case", lambda: fake_use_case)

    response = _post_interactivity(_block_action_payload("remove_buyer", buyer_id))

    assert response.status_code == 200
    assert len(fake_use_case.calls) == 1
    assert fake_use_case.calls[0][0] == (buyer_id, "U_TEST")
