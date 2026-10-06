"""AZM-133: every `/find-match` shows a popup listing missing or conflicting
buyer criteria; the match only starts when "Run anyway" is clicked.
"""

import logging
from dataclasses import dataclass
from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from app.modules.discrepancies.application.check import DiscrepancyCheckResult
from app.modules.discrepancies.domain.criteria import (
    BuyerCriteria,
    Discrepancy,
    DiscrepancyReport,
)
from app.modules.discrepancies.domain.vocabulary import Criterion
from app.modules.matching_engine.api import dependencies
from app.modules.matching_engine.api.slack.handlers import actions
from app.modules.matching_engine.api.slack.schemas import DiscrepancyGateMetadata
from app.modules.matching_engine.api.slack.views.discrepancy_gate import (
    build_discrepancy_gate_modal,
)

_GATE = DiscrepancyGateMetadata(
    buyer_role_id="buyer-1", channel_id="C1", requested_by="U1", advisor_context="UAE only"
)
_MISSING = DiscrepancyCheckResult(
    report=DiscrepancyReport(
        buyer_role_id="buyer-1",
        missing=(Discrepancy(Criterion.EBITDA, "missing", stored="(not set)"),),
    ),
    message="*Missing from Buyer's profile*\n• EBITDA floor (USD) / EBITDA ceiling (USD)",
    context_checked=True,
)
_CLEAR = DiscrepancyCheckResult(
    report=DiscrepancyReport(buyer_role_id="buyer-1"),
    message="No missing or conflicting details found for Buyer.",
    context_checked=True,
)
_CONFLICT = DiscrepancyCheckResult(
    report=DiscrepancyReport(
        buyer_role_id="buyer-1",
        conflicts=(Discrepancy(Criterion.VERTICAL, "conflict", stored="Garage", stated="Fintech"),),
    ),
    message=(
        "*Buyer's profile doesn't match your note*\n"
        "• Target vertical: profile has Garage, you said Fintech"
    ),
    context_checked=True,
)
_UNCHECKED = DiscrepancyCheckResult(
    report=DiscrepancyReport(buyer_role_id="buyer-1"),
    message=(
        "Nothing is missing from Buyer's profile, but your note couldn't be checked for conflicts."
    ),
    context_checked=False,
)


def test_gate_modal_runs_anyway_on_submit_and_round_trips_metadata() -> None:
    view = build_discrepancy_gate_modal(_GATE, _MISSING.message).to_dict()

    assert view["callback_id"] == "discrepancy_gate_modal"
    assert view["submit"]["text"] == "Run anyway"
    assert view["blocks"][0]["text"]["text"] == _MISSING.message
    assert DiscrepancyGateMetadata.model_validate_json(view["private_metadata"]) == _GATE


def test_gate_modal_cuts_a_long_message_at_a_line_break() -> None:
    message = "\n".join(f"• line {i:04d}" for i in range(400))
    view = build_discrepancy_gate_modal(_GATE, message).to_dict()

    text = view["blocks"][0]["text"]["text"]
    assert len(text) <= 3000
    assert message.startswith(text + "\n")


@dataclass
class _Harness:
    """Doubles as the fake Slack client: `_show_discrepancies` only calls `views_update`."""

    run: AsyncMock
    views_update: AsyncMock

    async def show(self) -> str:
        await actions._show_discrepancies(self, "V1", _GATE)  # ty: ignore[invalid-argument-type]
        return self.views_update.await_args.kwargs["view"].to_dict()["blocks"][0]["text"]["text"]


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> _Harness:
    run = AsyncMock()
    monkeypatch.setattr(actions, "run_match_and_post", run)
    monkeypatch.setattr(actions, "_MIN_UPDATE_DELAY_S", 0.0)
    return _Harness(run=run, views_update=AsyncMock())


def _check_returns(monkeypatch: pytest.MonkeyPatch, **kwargs: object) -> None:
    monkeypatch.setattr(actions, "find_buyer_discrepancies", AsyncMock(**kwargs))


@pytest.mark.parametrize(
    ("check", "expected_text"),
    [
        ({"return_value": _MISSING}, f"{_MISSING.message}\n\n{actions._FIX_FIRST_TEXT}"),
        ({"return_value": _CLEAR}, _CLEAR.message),
        # "Fill in the missing fields" only makes sense when a field is actually missing.
        ({"return_value": _CONFLICT}, _CONFLICT.message),
        ({"return_value": _UNCHECKED}, _UNCHECKED.message),
        ({"return_value": None}, actions._BUYER_GONE_TEXT),
        # A failed check must never read as an all-clear.
        ({"side_effect": RuntimeError("bedrock down")}, actions._CHECK_FAILED_TEXT),
    ],
)
async def test_popup_text_matches_the_check_outcome_and_never_runs(
    monkeypatch, harness, check, expected_text
) -> None:
    _check_returns(monkeypatch, **check)

    assert await harness.show() == expected_text
    harness.run.assert_not_awaited()


@pytest.mark.parametrize(
    ("slack_error", "level"), [("not_found", logging.INFO), ("ratelimited", logging.WARNING)]
)
async def test_only_a_closed_modal_is_logged_quietly(
    monkeypatch, harness, caplog, slack_error, level
) -> None:
    _check_returns(monkeypatch, return_value=_MISSING)
    harness.views_update.side_effect = SlackApiError(
        slack_error, {"ok": False, "error": slack_error}
    )

    with caplog.at_level(logging.INFO, logger=actions.logger.name):
        await actions._show_discrepancies(harness, "V1", _GATE)  # ty: ignore[invalid-argument-type]

    assert [r.levelno for r in caplog.records] == [level]
    harness.run.assert_not_awaited()


async def test_find_buyer_discrepancies_returns_the_check_result(monkeypatch) -> None:
    async def fake_check(_criteria: BuyerCriteria, _context: str | None) -> DiscrepancyCheckResult:
        return _CLEAR

    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", AsyncMock(return_value=object()))
    monkeypatch.setattr(
        "app.modules.matching_engine.providers.discrepancies.criteria_reader_adapter."
        "to_buyer_criteria",
        lambda buyer: buyer,
    )
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    assert await dependencies.find_buyer_discrepancies("buyer-1", None) is _CLEAR


async def test_find_buyer_discrepancies_returns_none_for_a_missing_buyer(monkeypatch) -> None:
    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", AsyncMock(return_value=None))

    assert await dependencies.find_buyer_discrepancies("buyer-1", None) is None
