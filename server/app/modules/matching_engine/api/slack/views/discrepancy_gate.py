"""The popup shown before every `/find-match` run: any missing or
conflicting buyer criteria, and "Run anyway" — the only way to start the
expensive matching workflow. Block Kit builders only, no logic.
"""

from slack_sdk.models.blocks import SectionBlock
from slack_sdk.models.views import View

from app.modules.matching_engine.api.slack.schemas import DiscrepancyGateMetadata

# Slack caps a section's text at 3,000 characters.
_MAX_SECTION_CHARS = 3000


def build_discrepancy_gate_modal(metadata: DiscrepancyGateMetadata, message: str) -> View:
    return View(
        type="modal",
        callback_id="discrepancy_gate_modal",
        private_metadata=metadata.model_dump_json(exclude_none=True),
        title="Before we match",
        submit="Run anyway",
        close="Cancel",
        blocks=[SectionBlock(text=message[:_MAX_SECTION_CHARS])],
    )
