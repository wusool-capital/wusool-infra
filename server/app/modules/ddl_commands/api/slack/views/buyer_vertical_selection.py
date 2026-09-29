"""Vertical step of `/add-buyer` and `/edit-buyer`, between organization
resolution and the field form. A buyer holds one role per vertical, so the
operator either picks a vertical the org already has a role for (edit it) or
one it doesn't (create it) — the same "existing entry or a create sentinel"
shape `organization_selection.py` uses for organizations.

The chosen action rides in the option value (`edit:<role_id>` /
`new:<vertical>`), so the submission handler routes without a database call.
"""

import json
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, TypeAdapter
from slack_sdk.models.blocks import InputBlock, SectionBlock
from slack_sdk.models.blocks.basic_components import Option, OptionGroup
from slack_sdk.models.blocks.block_elements import StaticSelectElement
from slack_sdk.models.views import View

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.notifications import sanitize_mrkdwn
from app.modules.utilities import get_shared_ephemeral_store

_EDIT_PREFIX = "edit:"
_NEW_PREFIX = "new:"
_NO_VERTICAL_LABEL = "No vertical set"
_NAMES = TypeAdapter(list[str])


class RoleRef(BaseModel):
    """An existing active buyer role, as much as this step needs of it."""

    role_id: str
    target_vertical: str | None = None


class VerticalSelectionMetadata(BaseModel):
    requested_by: str
    channel_id: str
    # `None` when the organization doesn't exist yet (the add form creates it).
    org_attio_id: str | None
    org_name: str
    # Names of similar orgs, shown as a warning on a brand-new org's form. A
    # token, not the names: the same growable-field reasoning as
    # `organization_selection`'s payload.
    duplicates_token: str | None = None


@dataclass(frozen=True)
class VerticalChoice:
    action: Literal["edit", "new"]
    value: str  # role id for "edit", vertical for "new"


def parse_vertical_choice(option_value: str) -> VerticalChoice:
    if option_value.startswith(_EDIT_PREFIX):
        return VerticalChoice("edit", option_value.removeprefix(_EDIT_PREFIX))
    if option_value.startswith(_NEW_PREFIX):
        return VerticalChoice("new", option_value.removeprefix(_NEW_PREFIX))
    raise ValueError(f"Unrecognised vertical option value: {option_value!r}")


def decode_duplicates(token: str | None) -> list[str]:
    """`[]` for a missing or expired token — losing the duplicate warning
    leaves a slightly less helpful form, not a broken submission."""
    if token is None:
        return []
    payload = get_shared_ephemeral_store().get(token)
    return [] if payload is None else _NAMES.validate_json(payload)


def build_buyer_vertical_selection_modal(
    *,
    org_attio_id: str | None,
    org_name: str,
    roles: list[RoleRef],
    requested_by: str,
    channel_id: str,
    duplicate_candidates: list[str] | None = None,
) -> View:
    verticals = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options
    used = {r.target_vertical for r in roles}

    groups: list[OptionGroup] = []
    existing = [
        Option(
            value=f"{_EDIT_PREFIX}{r.role_id}",
            text=f"{r.target_vertical or _NO_VERTICAL_LABEL} — edit"[:75],
        )
        for r in sorted(roles, key=lambda r: r.target_vertical or "")
    ]
    if existing:
        groups.append(OptionGroup(label="Existing roles", options=existing))
    unused = [
        Option(value=f"{_NEW_PREFIX}{v}", text=f"{v} — new role"[:75])
        for v in verticals
        if v not in used
    ]
    if unused:
        groups.append(OptionGroup(label="Add a vertical", options=unused))

    metadata = VerticalSelectionMetadata(
        requested_by=requested_by,
        channel_id=channel_id,
        org_attio_id=org_attio_id,
        org_name=org_name,
        duplicates_token=(
            get_shared_ephemeral_store().put(json.dumps(duplicate_candidates))
            if duplicate_candidates
            else None
        ),
    )
    return View(
        type="modal",
        callback_id="buyer_vertical_selection_modal",
        private_metadata=metadata.model_dump_json(),
        title="Buyer: vertical",
        submit="Continue",
        close="Cancel",
        blocks=[
            SectionBlock(
                text=(
                    f"Which vertical for *{sanitize_mrkdwn(org_name)}*? Pick an existing role "
                    "to edit it, or add a vertical to create a new role."
                )
            ),
            InputBlock(
                block_id="buyer_vertical",
                label="Vertical",
                element=StaticSelectElement(
                    action_id="selected_vertical",
                    option_groups=groups,
                    initial_option=existing[0] if existing else None,
                ),
            ),
        ],
    )
