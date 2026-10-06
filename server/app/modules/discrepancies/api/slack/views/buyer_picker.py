"""Buyer confirmation modal for `/check-buyer <name>` — mirrors
`matching_engine`'s own `buyer_selection.py`, narrowed to this module's
`BuyerCriteria`. Block Kit builders only, no logic.
"""

from slack_sdk.models.blocks import InputBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import PlainTextInputElement, StaticSelectElement
from slack_sdk.models.views import View

from app.modules.discrepancies.api.slack.schemas import CheckBuyerModalMetadata
from app.modules.discrepancies.domain.criteria import BuyerCriteria


def build_buyer_picker_modal(candidates: list[BuyerCriteria], *, channel_id: str) -> View:
    options = []
    for candidate in candidates:
        # HQ country disambiguates two orgs that would otherwise render
        # identically (same name, same/no vertical) — the search can
        # return more than one match for a name.
        name = (
            f"{candidate.org_name} ({candidate.org_hq_country})"
            if candidate.org_hq_country
            else candidate.org_name
        )
        label = f"{name} — {candidate.target_vertical or 'Generalist'}"
        options.append(Option(value=candidate.buyer_role_id, text=label[:75]))
    label = "Confirm this is the right buyer" if len(options) == 1 else "Choose the right buyer"

    return View(
        type="modal",
        callback_id="discrepancy_buyer_picker_modal",
        private_metadata=CheckBuyerModalMetadata(channel_id=channel_id).model_dump_json(),
        title="Check buyer",
        submit="Check",
        close="Cancel",
        blocks=[
            InputBlock(
                block_id="buyer_role_id",
                label=label,
                element=StaticSelectElement(
                    action_id="selected_buyer",
                    options=options,
                    initial_option=options[0],
                ),
            ),
            InputBlock(
                block_id="advisor_context",
                label="Anything specific about this search? (optional)",
                optional=True,
                element=PlainTextInputElement(
                    action_id="context_text",
                    multiline=True,
                    placeholder="e.g. pharma tech only, UAE, $5-15M ticket",
                ),
            ),
        ],
    )
