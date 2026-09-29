"""Renders a `DiscrepancyCheckResult` as Block Kit — Block Kit builders
only, no logic. `matching_engine` appends its own "Run match anyway" /
"Cancel" buttons after these blocks when there's a conflict; this module's
own `/check-buyer` posts them as-is.
"""

from slack_sdk.models.blocks import Block, SectionBlock
from slack_sdk.models.blocks.basic_components import MarkdownTextObject

from app.modules.discrepancies.application.check import DiscrepancyCheckResult


def build_discrepancy_blocks(result: DiscrepancyCheckResult) -> list[Block]:
    return [SectionBlock(text=MarkdownTextObject(text=result.message))]
