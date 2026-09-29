"""The "pause + buttons" message shown before a match runs when the
discrepancy check finds a conflict — the advisor confirms before the
expensive matching workflow proceeds. Block Kit builders only, no logic.
"""

from slack_sdk.models.blocks import ActionsBlock, Block, DividerBlock
from slack_sdk.models.blocks.block_elements import ButtonElement

from app.modules.discrepancies import DiscrepancyCheckResult, build_discrepancy_blocks
from app.modules.matching_engine.api.slack.schemas import RunAnywayValue


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
