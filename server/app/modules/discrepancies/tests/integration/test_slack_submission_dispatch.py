"""`/check-buyer` picker submission through this module's standalone app —
the typed `private_metadata` boundary, Slack redelivery, and what gets posted.
"""

import json
from collections.abc import Awaitable, Callable

import pytest

from app.modules.discrepancies.api.slack.handlers import actions as actions_module
from app.modules.discrepancies.api.slack.views.buyer_picker import build_buyer_picker_modal
from app.modules.discrepancies.application.check import DiscrepancyCheckResult
from app.modules.discrepancies.bootstrap import create_app
from app.modules.discrepancies.config import get_settings
from app.modules.discrepancies.domain.criteria import BuyerCriteria, DiscrepancyReport
from tests.slack_test_helpers import mock_slack_auth, post_interactivity

app = create_app()


class _RecordingRunner:
    def __init__(self) -> None:
        self.names: list[str] = []
        self.factories: list[Callable[[], Awaitable[None]]] = []

    def run(self, coro_factory: Callable[[], Awaitable[None]], *, name: str) -> None:
        self.names.append(name)
        self.factories.append(coro_factory)


class _FakeNotifier:
    def __init__(self) -> None:
        self.posted: list[dict] = []

    async def post_message(self, **kwargs: object) -> None:
        self.posted.append(kwargs)


def _submission(view_id: str, private_metadata: str, note: str | None = "  UAE only  ") -> dict:
    return {
        "type": "view_submission",
        "user": {"id": "U_TEST"},
        "view": {
            "type": "modal",
            "id": view_id,
            "callback_id": "discrepancy_buyer_picker_modal",
            "private_metadata": private_metadata,
            "state": {
                "values": {
                    "buyer_role_id": {"selected_buyer": {"selected_option": {"value": "role-1"}}},
                    "advisor_context": {"context_text": {"value": note}},
                }
            },
        },
    }


def _picker_metadata() -> str:
    candidate = BuyerCriteria(buyer_role_id="role-1", org_name="Acme", target_vertical=None)
    return build_buyer_picker_modal([candidate], channel_id="C_TEST").private_metadata or ""


@pytest.fixture
def runner(monkeypatch: pytest.MonkeyPatch) -> _RecordingRunner:
    mock_slack_auth(monkeypatch)
    recording = _RecordingRunner()
    monkeypatch.setattr(actions_module, "_task_runner", recording)
    return recording


def test_picker_metadata_round_trips_and_schedules_the_check(runner: _RecordingRunner) -> None:
    response = post_interactivity(
        app, get_settings().slack_signing_secret, _submission("V_OK", _picker_metadata())
    )

    assert response.status_code == 200
    assert runner.names == ["check-buyer:role-1"]


def test_redelivered_submission_runs_the_check_once(runner: _RecordingRunner) -> None:
    payload = _submission("V_DUP", _picker_metadata())
    for _ in range(2):
        post_interactivity(app, get_settings().slack_signing_secret, payload)

    assert runner.names == ["check-buyer:role-1"]


@pytest.mark.parametrize(
    "private_metadata", ["", "{}", "not json", json.dumps({"requested_by": "U1"})]
)
def test_invalid_metadata_is_dropped_without_running_a_check(
    runner: _RecordingRunner, private_metadata: str
) -> None:
    view_id = f"V_BAD_{private_metadata!r}"
    response = post_interactivity(
        app, get_settings().slack_signing_secret, _submission(view_id, private_metadata)
    )

    assert response.status_code == 200
    assert runner.names == []


def test_legacy_metadata_with_requested_by_still_parses(runner: _RecordingRunner) -> None:
    # A popup opened before this deploy still carries the dropped field.
    legacy = json.dumps({"requested_by": "U1", "channel_id": "C_TEST"})
    post_interactivity(app, get_settings().slack_signing_secret, _submission("V_LEGACY", legacy))

    assert runner.names == ["check-buyer:role-1"]


@pytest.mark.asyncio
async def test_check_and_post_posts_the_message_with_a_trimmed_note(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    notifier = _FakeNotifier()
    seen: list[tuple[str, str | None]] = []

    async def fake_check(buyer_role_id: str, context_text: str | None) -> DiscrepancyCheckResult:
        seen.append((buyer_role_id, context_text))
        report = DiscrepancyReport(buyer_role_id=buyer_role_id)
        return DiscrepancyCheckResult(report=report, message="All clear.", context_checked=True)

    monkeypatch.setattr(actions_module, "build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(actions_module, "check_buyer_by_id", fake_check)

    await actions_module._check_and_post("role-1", "UAE only", "C_TEST")

    assert seen == [("role-1", "UAE only")]
    assert notifier.posted[0]["channel"] == "C_TEST"
    assert notifier.posted[0]["text"] == "All clear."


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("outcome", "expected"),
    [(None, "Buyer not found."), (RuntimeError("db down"), "Discrepancy check failed")],
)
async def test_check_and_post_tells_the_channel_when_it_cannot_check(
    monkeypatch: pytest.MonkeyPatch, outcome: Exception | None, expected: str
) -> None:
    notifier = _FakeNotifier()

    async def fake_check(buyer_role_id: str, context_text: str | None) -> None:
        if isinstance(outcome, Exception):
            raise outcome
        return outcome

    monkeypatch.setattr(actions_module, "build_slack_notifier", lambda: notifier)
    monkeypatch.setattr(actions_module, "check_buyer_by_id", fake_check)

    await actions_module._check_and_post("role-1", None, "C_TEST")

    assert len(notifier.posted) == 1
    assert str(notifier.posted[0]["text"]).startswith(expected)
