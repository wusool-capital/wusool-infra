"""The "pause + buttons" message shown before a match runs when the
discrepancy check finds a conflict — the advisor confirms before the
expensive matching workflow proceeds. Block Kit builders only, no logic.
"""

from slack_sdk.models.blocks import ActionsBlock, Block, DividerBlock, SectionBlock
from slack_sdk.models.blocks.block_elements import ButtonElement
from slack_sdk.models.views import View

from app.modules.discrepancies import DiscrepancyCheckResult, build_discrepancy_blocks
from app.modules.matching_engine.api.slack.schemas import DiscrepancyGateMetadata, RunAnywayValue

# Slack caps a section's text at 3,000 characters.
_MAX_SECTION_CHARS = 3000


def build_discrepancy_gate_blocks(
    buyer_role_id: str, result: DiscrepancyCheckResult, advisor_context: str | None = None
) -> list[Block]:
    blocks = build_discrepancy_blocks(result)
    run_value = RunAnywayValue(
        buyer_role_id=buyer_role_id, advisor_context=advisor_context
    ).model_dump_json()
    blocks.append(DividerBlock())
    blocks.append(
        ActionsBlock(
            block_id=f"discrepancy_gate_{buyer_role_id}",
            elements=[
                ButtonElement(
                    text="Run match anyway",
                    action_id="discrepancy_run_match",
                    style="primary",
                    value=run_value,
                ),
                ButtonElement(text="Cancel", action_id="discrepancy_cancel", value=buyer_role_id),
            ],
        )
    )
    return blocks


def build_discrepancy_gate_modal(metadata: DiscrepancyGateMetadata, message: str) -> View:
    """Popup shown before every `/find-match` run, listing any missing or
    conflicting criteria. Submitting ("Run anyway") is the only way to start it."""
    return View(
        type="modal",
        callback_id="discrepancy_gate_modal",
        private_metadata=metadata.model_dump_json(exclude_none=True),
        title="Before we match",
        submit="Run anyway",
        close="Cancel",
        blocks=[SectionBlock(text=message[:_MAX_SECTION_CHARS])],
    )
