"""`/enrich <name>` step 1, only shown when the fuzzy match is ambiguous —
one org can carry both an active seller role and an active buyer role, or
several orgs can match the typed name. Mirrors `ddl_commands`'
`organization_selection.py` shape.
"""

import json

from slack_sdk.models.blocks import InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.modules.enrichment.domain.targets import ResolvedOrgRole
from app.modules.notifications import sanitize_mrkdwn


def build_role_selection_modal(
    candidates: list[ResolvedOrgRole], *, search_term: str, requested_by: str, channel_id: str
) -> View:
    options = [
        Option(value=f"{c.kind}:{c.role_id}", text=f"{c.org_name} ({c.kind})"[:75])
        for c in candidates
    ]
    return View(
        type="modal",
        callback_id="enrichment_role_selection_modal",
        private_metadata=json.dumps(
            {"requested_by": requested_by, "channel_id": channel_id, "search_term": search_term}
        ),
        title="Enrich",
        submit="Continue",
        close="Cancel",
        blocks=[
            SectionBlock(
                text=f"Found {len(candidates)} match(es) for "
                f"*{sanitize_mrkdwn(search_term)}*. Pick one to enrich."
            ),
            InputBlock(
                block_id="role_id",
                label="Buyer/seller",
                element=StaticSelectElement(
                    action_id="selected_role", options=options, initial_option=options[0]
                ),
            ),
        ],
    )
