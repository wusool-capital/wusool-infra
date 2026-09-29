"""The "pause + buttons" message shown before a match runs when the
discrepancy check finds a conflict — the advisor confirms before the
expensive matching workflow proceeds. Block Kit builders only, no logic.
"""

from slack_sdk.models.blocks import ActionsBlock, Block, DividerBlock
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.discrepancies import DiscrepancyCheckResult, build_discrepancy_blocks


def build_discrepancy_gate_blocks(
    buyer_role_id: str, result: DiscrepancyCheckResult
) -> list[Block]:
    blocks = build_discrepancy_blocks(result)
    blocks.append(DividerBlock())
    blocks.append(
        ActionsBlock(
            block_id=f"discrepancy_gate_{buyer_role_id}",
            elements=[
                ButtonElement(
                    text="Run match anyway",
                    action_id="discrepancy_run_match",
                    style="primary",
                    value=buyer_role_id,
                ),
                ButtonElement(text="Cancel", action_id="discrepancy_cancel", value=buyer_role_id),
            ],
        )
    )
    return blocks
