"""`/enrich-seller`/`/enrich-buyer` step 1, only shown when the fuzzy match
is ambiguous within that one kind — several distinct orgs matching the
typed name, each with an active role of the kind asked for. Mirrors
`ddl_commands`' `organization_selection.py` shape.
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
    # Every candidate shares the same kind — `/enrich-seller`/`/enrich-buyer`
    # already filtered by it before this modal is ever shown — so the only
    # remaining ambiguity is *which organization*, not which role.
    options = [Option(value=f"{c.kind}:{c.role_id}", text=c.org_name[:75]) for c in candidates]
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
                label="Organization",
                element=StaticSelectElement(
                    action_id="selected_role", options=options, initial_option=options[0]
                ),
            ),
        ],
    )
