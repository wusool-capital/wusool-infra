"""The popup shown before every `/find-match` run: any missing or
conflicting buyer criteria, and "Run anyway" — the only way to start the
expensive matching workflow. Block Kit builders only, no logic.
"""

from slack_sdk.models.blocks import ActionsBlock, Block, SectionBlock
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.views import View

from app.modules.matching_engine.api.slack.schemas import DiscrepancyGateMetadata

# Slack caps a section's text at 3,000 characters.
_MAX_SECTION_CHARS = 3000


def _fit(message: str) -> str:
    """Cuts at a line break so a long message never ends mid-bullet."""
    if len(message) <= _MAX_SECTION_CHARS:
        return message
    cut = message.rfind("\n", 0, _MAX_SECTION_CHARS)
    return message[: cut if cut > 0 else _MAX_SECTION_CHARS]


def build_discrepancy_gate_modal(
    metadata: DiscrepancyGateMetadata, message: str, *, offer_edit: bool = False
) -> View:
    blocks: list[Block] = [SectionBlock(text=_fit(message))]
    if offer_edit:
        # Handled by `ddl_commands` (it owns the edit-buyer flow); a modal's
        # footer can't hold a third button, so this lives in the body.
        blocks.append(
            ActionsBlock(
                elements=[
                    ButtonElement(
                        action_id="edit_buyer_from_gate",
                        text="Edit buyer",
                        value=metadata.buyer_role_id,
                    )
                ]
            )
        )
    return View(
        type="modal",
        callback_id="discrepancy_gate_modal",
        private_metadata=metadata.model_dump_json(exclude_none=True),
        title="Before we match",
        submit="Run anyway",
        close="Cancel",
        blocks=blocks,
    )
