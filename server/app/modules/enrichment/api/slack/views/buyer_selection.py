"""`/enrich-buyer` two-step picker, mirroring `/edit-buyer`: organization
first, then the vertical. A buyer holds one role per vertical, so the org
alone doesn't identify what to enrich.

The candidate roles ride in a server-side token (same reasoning as
`ddl_commands`' `organization_selection.py`), not in `private_metadata`.
"""

from pydantic import BaseModel, TypeAdapter
from slack_sdk.models.blocks import InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.modules.enrichment.domain.targets import ResolvedOrgRole
from app.modules.notifications import sanitize_mrkdwn
from app.modules.utilities import get_shared_ephemeral_store

_ROLES = TypeAdapter(list[ResolvedOrgRole])
_NO_VERTICAL_LABEL = "Generalist"
_MAX_SELECT_OPTIONS = 100  # Slack's static-select limit


class BuyerSelectionMetadata(BaseModel):
    requested_by: str
    channel_id: str
    roles_token: str


def encode_roles(roles: list[ResolvedOrgRole]) -> str:
    return get_shared_ephemeral_store().put(_ROLES.dump_json(roles).decode())


def decode_roles(token: str) -> list[ResolvedOrgRole] | None:
    """`None` for an expired or unknown token."""
    payload = get_shared_ephemeral_store().get(token)
    return None if payload is None else _ROLES.validate_json(payload)


def build_buyer_organization_modal(
    roles: list[ResolvedOrgRole], *, search_term: str, requested_by: str, channel_id: str
) -> View:
    orgs = {r.org_attio_id: r.org_name for r in roles}
    options = [Option(value=attio_id, text=name[:75]) for attio_id, name in orgs.items()]
    return View(
        type="modal",
        callback_id="enrichment_buyer_organization_modal",
        private_metadata=BuyerSelectionMetadata(
            requested_by=requested_by, channel_id=channel_id, roles_token=encode_roles(roles)
        ).model_dump_json(),
        title="Enrich buyer",
        submit="Continue",
        close="Cancel",
        blocks=[
            SectionBlock(
                text=f"Found {len(options)} organization(s) matching "
                f"*{sanitize_mrkdwn(search_term)}*. Pick one to enrich."
            ),
            InputBlock(
                block_id="organization_id",
                label="Organization",
                element=StaticSelectElement(
                    action_id="selected_organization", options=options, initial_option=options[0]
                ),
            ),
        ],
    )


def build_buyer_vertical_modal(
    roles: list[ResolvedOrgRole], *, requested_by: str, channel_id: str
) -> View:
    """`roles` are all one organization's active buyer roles."""
    options: list[Option] = []
    seen: dict[str, int] = {}
    for r in sorted(roles, key=lambda r: r.target_vertical or "")[:_MAX_SELECT_OPTIONS]:
        label = r.target_vertical or _NO_VERTICAL_LABEL
        # Two roles can share a vertical (or both have none); number repeats so
        # the operator can tell them apart.
        seen[label] = seen.get(label, 0) + 1
        text = label if seen[label] == 1 else f"{label} ({seen[label]})"
        options.append(Option(value=r.role_id, text=text[:75]))
    return View(
        type="modal",
        callback_id="enrichment_buyer_vertical_modal",
        private_metadata=BuyerSelectionMetadata(
            requested_by=requested_by, channel_id=channel_id, roles_token=encode_roles(roles)
        ).model_dump_json(),
        title="Buyer: vertical",
        submit="Enrich",
        close="Cancel",
        blocks=[
            SectionBlock(
                text=f"Which vertical for *{sanitize_mrkdwn(roles[0].org_name)}*? "
                "Each vertical is a separate buyer role."
            ),
            InputBlock(
                block_id="buyer_vertical",
                label="Vertical",
                element=StaticSelectElement(
                    action_id="selected_vertical", options=options, initial_option=options[0]
                ),
            ),
        ],
    )
