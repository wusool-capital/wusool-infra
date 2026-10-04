"""AZM-133: every `/find-match` shows a popup listing missing or conflicting
buyer criteria; the match only starts when "Run anyway" is clicked.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from app.modules.discrepancies.application.check import DiscrepancyCheckResult
from app.modules.discrepancies.domain.criteria import Discrepancy, DiscrepancyReport
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
    message="Hey! Just a heads up, EBITDA is missing.",
)


def test_gate_modal_runs_anyway_on_submit_and_round_trips_metadata() -> None:
    view = build_discrepancy_gate_modal(_GATE, _MISSING.message).to_dict()

    assert view["callback_id"] == "discrepancy_gate_modal"
    assert view["submit"]["text"] == "Run anyway"
    assert view["blocks"][0]["text"]["text"] == _MISSING.message
    assert DiscrepancyGateMetadata.model_validate_json(view["private_metadata"]) == _GATE


@pytest.fixture
def harness(monkeypatch: pytest.MonkeyPatch) -> SimpleNamespace:
    run = AsyncMock()
    client = SimpleNamespace(views_update=AsyncMock())
    monkeypatch.setattr(actions, "run_match_and_post", run)
    return SimpleNamespace(run=run, client=client)


@pytest.mark.parametrize(
    ("findings", "expected_text"),
    [(_MISSING, _MISSING.message), (None, actions._CLEAR_TEXT)],
)
async def test_check_fills_the_popup_and_never_runs_the_match(
    monkeypatch, harness, findings, expected_text
) -> None:
    monkeypatch.setattr(actions, "find_buyer_discrepancies", AsyncMock(return_value=findings))

    await actions._show_discrepancies(harness.client, "V1", _GATE)

    view = harness.client.views_update.await_args.kwargs["view"].to_dict()
    assert view["callback_id"] == "discrepancy_gate_modal"
    assert view["blocks"][0]["text"]["text"] == expected_text
    harness.run.assert_not_awaited()


async def test_closed_modal_is_logged_not_raised(monkeypatch, harness) -> None:
    monkeypatch.setattr(actions, "find_buyer_discrepancies", AsyncMock(return_value=_MISSING))
    harness.client.views_update.side_effect = SlackApiError("not_found", {"ok": False})

    await actions._show_discrepancies(harness.client, "V1", _GATE)

    harness.run.assert_not_awaited()


@pytest.mark.parametrize(
    ("report", "expected"),
    [
        (DiscrepancyReport(buyer_role_id="buyer-1"), None),
        (_MISSING.report, _MISSING.message),
    ],
)
async def test_find_buyer_discrepancies_returns_only_actionable_findings(
    monkeypatch, report, expected
) -> None:
    async def fake_check(_criteria, _context):  # noqa: ANN001, ANN202
        return DiscrepancyCheckResult(report=report, message=_MISSING.message)

    monkeypatch.setattr(dependencies, "resolve_buyer_by_id", AsyncMock(return_value=object()))
    monkeypatch.setattr(
        "app.modules.matching_engine.providers.discrepancies.criteria_reader_adapter."
        "to_buyer_criteria",
        lambda buyer: buyer,
    )
    monkeypatch.setattr("app.modules.discrepancies.check_buyer_discrepancies", fake_check)

    result = await dependencies.find_buyer_discrepancies("buyer-1", None)

    assert (result.message if result else None) == expected


async def test_find_buyer_discrepancies_never_raises(monkeypatch) -> None:
    monkeypatch.setattr(
        dependencies, "resolve_buyer_by_id", AsyncMock(side_effect=RuntimeError("db down"))
    )

    assert await dependencies.find_buyer_discrepancies("buyer-1", None) is None
