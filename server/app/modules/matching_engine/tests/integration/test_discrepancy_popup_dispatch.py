"""AZM-133: signed view submissions through Bolt for the buyer-selection
modal (which becomes the discrepancy popup) and its "Run anyway" submit.
"""

import json
from collections.abc import Callable, Coroutine
from dataclasses import dataclass, field

import pytest
from httpx import Response

from app.modules.matching_engine.api.slack.handlers import actions as actions_module
from app.modules.matching_engine.bootstrap import create_app
from app.modules.matching_engine.config import get_settings
from tests.slack_test_helpers import mock_slack_auth, post_interactivity

app = create_app()

_SELECTED_BUYER = {"buyer_role_id": {"selected_buyer": {"selected_option": {"value": "buyer-1"}}}}
_SELECTION_METADATA = json.dumps({"requested_by": "U_TEST", "channel_id": "C_TEST"})


@dataclass(frozen=True)
class _MatchRun:
    buyer_role_id: str
    requested_by: str
    channel_id: str
    advisor_context: str | None


@dataclass
class _Dispatched:
    task_names: list[str] = field(default_factory=list)
    match_runs: list[_MatchRun] = field(default_factory=list)


def _submission(
    callback_id: str, view_id: str, private_metadata: str, values: dict[str, dict]
) -> dict[str, object]:
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


def _post(payload: dict[str, object]) -> Response:
    # The shared helper is annotated as returning the client; it returns the response.
    response = post_interactivity(app, get_settings().slack_signing_secret, payload)
    assert isinstance(response, Response)
    return response


@pytest.fixture
def dispatched(monkeypatch: pytest.MonkeyPatch) -> _Dispatched:
    record = _Dispatched()

    async def fake_run_match_and_post(
        buyer_role_id: str, requested_by: str, channel_id: str, *, advisor_context: str | None
    ) -> None:
        pass

    def recording_run_match_and_post(
        buyer_role_id: str, requested_by: str, channel_id: str, *, advisor_context: str | None
    ) -> Coroutine[None, None, None]:
        record.match_runs.append(
            _MatchRun(buyer_role_id, requested_by, channel_id, advisor_context)
        )
        return fake_run_match_and_post(
            buyer_role_id, requested_by, channel_id, advisor_context=advisor_context
        )

    def fake_run(coro_factory: Callable[[], Coroutine[None, None, None]], *, name: str) -> None:
        record.task_names.append(name)
        coro_factory().close()  # never awaited — no Slack or Bedrock calls

    mock_slack_auth(monkeypatch)
    monkeypatch.setattr(actions_module, "run_match_and_post", recording_run_match_and_post)
    monkeypatch.setattr(actions_module._task_runner, "run", fake_run)
    return record


def test_buyer_selection_opens_the_run_anyway_popup_without_matching(dispatched) -> None:
    payload = _submission("buyer_selection_modal", "V_SELECT", _SELECTION_METADATA, _SELECTED_BUYER)

    response = _post(payload)

    assert response.status_code == 200
    body = response.json()
    assert body["response_action"] == "update"
    # The first popup already carries the button, so a lost update can't strand it.
    assert body["view"]["callback_id"] == "discrepancy_gate_modal"
    assert body["view"]["submit"]["text"] == "Run anyway"
    assert dispatched.task_names == ["find-match-check:buyer-1"]
    assert dispatched.match_runs == []


def test_malformed_buyer_selection_acks_and_can_be_retried(dispatched) -> None:
    broken = _submission("buyer_selection_modal", "V_RETRY", "not json", _SELECTED_BUYER)
    fixed = _submission("buyer_selection_modal", "V_RETRY", _SELECTION_METADATA, _SELECTED_BUYER)

    first = _post(broken)
    second = _post(fixed)

    assert first.status_code == 200
    assert second.json()["response_action"] == "update"
    assert dispatched.task_names == ["find-match-check:buyer-1"]


def test_run_anyway_starts_the_match(dispatched) -> None:
    metadata = {"buyer_role_id": "buyer-1", "channel_id": "C_TEST", "requested_by": "U_TEST"}
    payload = _submission("discrepancy_gate_modal", "V_GATE", json.dumps(metadata), {})

    response = _post(payload)

    assert response.status_code == 200
    assert dispatched.match_runs == [_MatchRun("buyer-1", "U_TEST", "C_TEST", None)]


def test_run_anyway_with_bad_metadata_runs_nothing(dispatched) -> None:
    payload = _submission("discrepancy_gate_modal", "V_BAD", "not json", {})

    response = _post(payload)

    assert response.status_code == 200
    assert dispatched.task_names == []
