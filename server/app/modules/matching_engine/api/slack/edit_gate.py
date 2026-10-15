"""Implements `ddl_commands`' `EditGatePort` for `/find-match`'s "Before we match"
popup: while an `/edit-buyer` form opened from it is saving, "Run anyway" is
taken away, and once the write ends the buyer is checked again so the popup
shows what is true now. `server/main.py` wires it; this module never imports
`ddl_commands`.
"""

import logging

from pydantic import ValidationError
from slack_sdk.errors import SlackApiError

from app.modules.matching_engine.api.slack.handlers.actions import show_discrepancies
from app.modules.matching_engine.api.slack.schemas import DiscrepancyGateMetadata
from app.modules.matching_engine.api.slack.views.discrepancy_gate import (
    build_discrepancy_gate_modal,
)
from app.modules.matching_engine.config import get_settings
from app.modules.notifications import get_slack_client

logger = logging.getLogger(__name__)

_SAVING_TEXT = ":hourglass_flowing_sand: _Saving your changes…_"


def _gate(gate_state: str) -> DiscrepancyGateMetadata | None:
    try:
        return DiscrepancyGateMetadata.model_validate_json(gate_state)
    except ValidationError:
        logger.warning("edit_gate_invalid_state")
        return None


class MatchingEngineEditGate:
    async def saving(self, *, gate_view_id: str, gate_state: str) -> None:
        if (gate := _gate(gate_state)) is None:
            return
        client = get_slack_client(get_settings().slack_bot_token)
        try:
            await client.views_update(
                view_id=gate_view_id,
                view=build_discrepancy_gate_modal(gate, _SAVING_TEXT, saving=True),
            )
        except SlackApiError:
            # Closed in the meantime; nothing left to lock.
            logger.info("edit_gate_popup_gone view_id=%s", gate_view_id)

    async def finished(self, *, gate_view_id: str, gate_state: str) -> None:
        if (gate := _gate(gate_state)) is None:
            return
        client = get_slack_client(get_settings().slack_bot_token)
        await show_discrepancies(client, gate_view_id, gate)
