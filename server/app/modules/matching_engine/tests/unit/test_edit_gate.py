"""While an edit form saves over `/find-match`'s popup, "Run anyway" is taken
away; once the write ends the buyer is checked again."""

from unittest.mock import AsyncMock

import pytest
from slack_sdk.errors import SlackApiError

from app.modules.matching_engine.api.slack import edit_gate as edit_gate_module
from app.modules.matching_engine.api.slack.edit_gate import MatchingEngineEditGate
from app.modules.matching_engine.api.slack.schemas import DiscrepancyGateMetadata
from app.modules.matching_engine.api.slack.views.discrepancy_gate import (
    build_discrepancy_gate_modal,
)

_GATE = DiscrepancyGateMetadata(
    buyer_role_id="buyer-1", channel_id="C1", requested_by="U1", advisor_context="UAE only"
)


def test_the_saving_popup_has_no_run_anyway_and_no_edit_button() -> None:
    view = build_discrepancy_gate_modal(_GATE, "Saving…", offer_edit=True, saving=True).to_dict()

    assert "submit" not in view
    assert all(block["type"] != "actions" for block in view["blocks"])


def test_the_normal_popup_still_has_run_anyway() -> None:
    view = build_discrepancy_gate_modal(_GATE, "Missing", offer_edit=True).to_dict()

    assert view["submit"]["text"] == "Run anyway"


@pytest.fixture
def client(monkeypatch) -> AsyncMock:
    fake = AsyncMock()
    monkeypatch.setattr(edit_gate_module, "get_slack_client", lambda _token: fake)
    monkeypatch.setattr(
        edit_gate_module, "get_settings", lambda: type("S", (), {"slack_bot_token": "x"})()
    )
    return fake


async def test_saving_locks_the_popup(client: AsyncMock) -> None:
    await MatchingEngineEditGate().saving(
        gate_view_id="V_GATE", gate_state=_GATE.model_dump_json(exclude_none=True)
    )

    sent = client.views_update.await_args.kwargs
    assert sent["view_id"] == "V_GATE"
    assert "submit" not in sent["view"].to_dict()


async def test_saving_survives_a_popup_that_was_closed(client: AsyncMock) -> None:
    client.views_update.side_effect = SlackApiError("gone", {"error": "not_found"})

    await MatchingEngineEditGate().saving(
        gate_view_id="V_GATE", gate_state=_GATE.model_dump_json(exclude_none=True)
    )


async def test_finishing_rechecks_the_buyer_on_the_same_popup(
    client: AsyncMock, monkeypatch
) -> None:
    show = AsyncMock()
    monkeypatch.setattr(edit_gate_module, "show_discrepancies", show)

    await MatchingEngineEditGate().finished(
        gate_view_id="V_GATE", gate_state=_GATE.model_dump_json(exclude_none=True)
    )

    show.assert_awaited_once_with(client, "V_GATE", _GATE)


async def test_an_unreadable_state_changes_nothing(client: AsyncMock) -> None:
    await MatchingEngineEditGate().saving(gate_view_id="V_GATE", gate_state="not json")

    client.views_update.assert_not_awaited()
