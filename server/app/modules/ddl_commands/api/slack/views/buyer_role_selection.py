"""Organization disambiguation modal for `/edit-buyer` — one option per
organization, since a buyer now holds a role per vertical and the vertical
step (`buyer_vertical_selection.py`) is where the role gets picked.

Named (and callback_id'd) `buyer_role_selection`, not `buyer_selection` —
matching-engine's own `/find-match` already has an unrelated
`buyer_selection_modal` (its own match-target disambiguation). Since both
bots now run in one process on one `AsyncApp`, a shared callback_id would
mean two Bolt listeners registered for the same view submission with no way
to tell which payload belongs to which handler.
"""

import json

from pydantic import BaseModel
from slack_sdk.models.blocks import InputBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.modules.ddl_commands.api.buyers import BuyerSummary
from app.modules.ddl_commands.api.schemas import OrganizationSummary
from app.modules.ddl_commands.api.slack.views.buyer_vertical_selection import RoleRef
from app.modules.utilities import get_shared_ephemeral_store


class OrgRolesPayload(BaseModel):
    """Every matched org's active roles, by org id. Server-side because ten
    orgs of up to ~16 roles each overrun `private_metadata`'s 3000 chars."""

    roles_by_org: dict[str, list[RoleRef]]


def decode_org_roles(token: str | None) -> dict[str, list[RoleRef]]:
    """`{}` for a missing or expired token; the submission handler treats an
    org it can't find roles for as "could not be found"."""
    if token is None:
        return {}
    payload = get_shared_ephemeral_store().get(token)
    if payload is None:
        return {}
    return OrgRolesPayload.model_validate_json(payload).roles_by_org


def build_buyer_selection_modal(
    candidates: list[BuyerSummary], *, requested_by: str, channel_id: str
) -> View:
    """`candidates` are the matched orgs' active roles, best-matching org
    first; roles of one org are adjacent."""
    roles_by_org: dict[str, list[RoleRef]] = {}
    orgs: dict[str, OrganizationSummary] = {}
    for candidate in candidates:
        org = candidate.organization
        orgs.setdefault(org.attio_id, org)
        roles_by_org.setdefault(org.attio_id, []).append(
            RoleRef(role_id=str(candidate.id), target_vertical=candidate.target_vertical)
        )

    options = []
    for org in orgs.values():
        detail_bits = [b for b in (org.hq_country, ", ".join(org.sector_focus) or None) if b]
        detail = f" ({', '.join(detail_bits)})" if detail_bits else ""
        options.append(Option(value=org.attio_id, text=f"{org.name}{detail}"[:75]))

    label = (
        "Confirm this is the right buyer to edit"
        if len(options) == 1
        else "Choose the right buyer to edit"
    )

    return View(
        type="modal",
        callback_id="buyer_role_selection_modal",
        # See `seller_role_selection.py` — `org_names` exists so the submission
        # handler can `ack()` inside Slack's 3s window without a database query.
        private_metadata=json.dumps(
            {
                "requested_by": requested_by,
                "channel_id": channel_id,
                "org_names": {attio_id: org.name for attio_id, org in orgs.items()},
                "payload_token": get_shared_ephemeral_store().put(
                    OrgRolesPayload(roles_by_org=roles_by_org).model_dump_json()
                ),
            }
        ),
        title="Confirm buyer",
        submit="Continue",
        close="Cancel",
        blocks=[
            InputBlock(
                block_id="buyer_role_id",
                label=label,
                element=StaticSelectElement(
                    action_id="selected_buyer", options=options, initial_option=options[0]
                ),
            )
        ],
    )
