"""AZM-133: signed view submissions through Bolt for the buyer-selection
modal (which becomes the discrepancy popup) and its "Run anyway" submit.
"""

import json

import pytest

from app.modules.matching_engine.api.slack.handlers import actions as actions_module
from app.modules.matching_engine.bootstrap import create_app
from app.modules.matching_engine.config import get_settings
from tests.slack_test_helpers import mock_slack_auth, post_interactivity

app = create_app()


def _submission(callback_id: str, view_id: str, private_metadata: str, values: dict) -> dict:
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": view_id,
            "callback_id": callback_id,
            "private_metadata": private_metadata,
            "state": {"values": values},
        },
    }


@pytest.fixture
def dispatched(monkeypatch: pytest.MonkeyPatch) -> dict:
    record: dict = {"names": [], "runs": []}

    async def _noop() -> None:
        pass

    def fake_run_match_and_post(*args: object, **kwargs: object):  # noqa: ANN202
        record["runs"].append((args, kwargs))
        return _noop()

    def fake_run(coro_factory, *, name: str) -> None:  # noqa: ANN001
        record["names"].append(name)
        coro = coro_factory()
        coro.close()  # never awaited — no Slack or Bedrock calls

    mock_slack_auth(monkeypatch)
    monkeypatch.setattr(actions_module, "run_match_and_post", fake_run_match_and_post)
    monkeypatch.setattr(actions_module._task_runner, "run", fake_run)
    return record


def test_buyer_selection_opens_the_run_anyway_popup_without_matching(dispatched) -> None:
    payload = _submission(
        "buyer_selection_modal",
        "V_SELECT",
        json.dumps({"requested_by": "U_TEST", "channel_id": "C_TEST"}),
        {"buyer_role_id": {"selected_buyer": {"selected_option": {"value": "buyer-1"}}}},
    )

    response = post_interactivity(app, get_settings().slack_signing_secret, payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    # The first popup already carries the button, so a lost update can't strand it.
    assert body["view"]["callback_id"] == "discrepancy_gate_modal"
    assert body["view"]["submit"]["text"] == "Run anyway"
    assert dispatched["names"] == ["find-match-check:buyer-1"]
    assert dispatched["runs"] == []


def test_run_anyway_starts_the_match_without_rechecking(dispatched) -> None:
    metadata = {"buyer_role_id": "buyer-1", "channel_id": "C_TEST", "requested_by": "U_TEST"}
    payload = _submission("discrepancy_gate_modal", "V_GATE", json.dumps(metadata), {})

    response = post_interactivity(app, get_settings().slack_signing_secret, payload)

    assert response.status_code == 200
    assert dispatched["runs"] == [
        (
            ("buyer-1", "U_TEST", "C_TEST"),
            {"advisor_context": None, "check_discrepancies": False},
        )
    ]


def test_run_anyway_with_bad_metadata_runs_nothing(dispatched) -> None:
    payload = _submission("discrepancy_gate_modal", "V_BAD", "not json", {})

    response = post_interactivity(app, get_settings().slack_signing_secret, payload)

    assert response.status_code == 200
    assert dispatched["names"] == []
