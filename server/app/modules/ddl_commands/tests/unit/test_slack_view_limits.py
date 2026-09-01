"""Every modal we build, checked against Slack's view limits.

Nothing here is hypothetical: the field-picker shipped with 15 checkbox
options against Slack's cap of 10, which broke `/edit-seller` and
`/edit-buyer` outright. Slack rejects an over-limit view *silently* from our
side — the modal shows "We had some trouble connecting", we log a clean 200
and raise nothing — so it can only be caught here, before it's sent.
"""

import json
import uuid
from types import SimpleNamespace

import pytest

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS
from app.modules.ddl_commands.api.slack.views.buyer_add_form import build_buyer_add_form_modal
from app.modules.ddl_commands.api.slack.views.buyer_form import build_buyer_edit_form_modal
from app.modules.ddl_commands.api.slack.views.buyer_role_selection import (
    build_buyer_selection_modal,
)
from app.modules.ddl_commands.api.slack.views.field_picker import build_field_picker_modal
from app.modules.ddl_commands.api.slack.views.seller_add_form import build_seller_add_form_modal
from app.modules.ddl_commands.api.slack.views.seller_form import build_seller_edit_form_modal
from app.modules.ddl_commands.api.slack.views.seller_role_selection import (
    build_seller_selection_modal,
)

# https://docs.slack.dev/reference/block-kit — the caps that bite us.
_MAX_OPTIONS = {"checkboxes": 10, "static_select": 100, "multi_static_select": 100}
_MAX_BLOCKS = 100
_MAX_PRIVATE_METADATA = 3000
_MAX_TITLE = 24
_MAX_OPTION_TEXT = 75


def assert_valid_view(view: dict) -> None:
    for key in ("title", "submit", "close"):
        if key in view:
            assert len(view[key]["text"]) <= _MAX_TITLE, f"{key} too long: {view[key]['text']}"
    assert len(json.dumps(view["blocks"])) < 10**7
    assert len(view["blocks"]) <= _MAX_BLOCKS
    assert len(view.get("private_metadata", "")) <= _MAX_PRIVATE_METADATA

    for block in view["blocks"]:
        element = block.get("element") or block.get("accessory")
        if not element:
            continue
        options = element.get("options")
        if options is None:
            continue
        cap = _MAX_OPTIONS.get(element["type"])
        assert cap is not None, f"unhandled element type {element['type']}"
        assert len(options) <= cap, (
            f"{element['action_id']}: {len(options)} options exceeds "
            f"Slack's {cap} for {element['type']}"
        )
        for option in options:
            assert len(option["text"]["text"]) <= _MAX_OPTION_TEXT


@pytest.mark.parametrize(
    ("kind", "role_fields"),
    [("seller", SELLER_ROLE_FIELDS), ("buyer", BUYER_ROLE_FIELDS)],
)
def test_field_picker_modal_is_within_slack_limits(kind, role_fields):
    assert_valid_view(
        build_field_picker_modal(
            kind=kind,
            role_id="role-1",
            org_name="Some Organization",
            requested_by="U1",
            channel_id="C1",
            role_fields=role_fields,
        ).to_dict()
    )


class _Org:
    def __init__(self, name):
        self.name = name
        self.hq_country = "AE"
        self.sector_focus = ["Logistics"]


class _Candidate:
    def __init__(self, id_, name):
        self.id = id_
        self.organization = _Org(name)


@pytest.mark.parametrize("build", [build_seller_selection_modal, build_buyer_selection_modal])
def test_selection_modal_is_within_slack_limits(build):
    # `org_names` rides in private_metadata, which Slack caps at 3000 bytes —
    # so the candidate list is what has to stay bounded, not just the options.
    candidates = [_Candidate(f"role-{i}", f"Organization Number {i}") for i in range(25)]
    assert_valid_view(build(candidates, requested_by="U1", channel_id="C1").to_dict())


# `sector_focus` alone carries 85 of Slack's 100 permitted options, and an
# over-limit view is rejected silently. Without these, growing that list by 16
# would break every `/add-buyer` and `/add-seller` with nothing to catch it.


def _row(fields, **overrides):
    row = SimpleNamespace(**{f.name: None for f in fields})
    for key, value in overrides.items():
        setattr(row, key, value)
    return row


def _org_row(**overrides):
    return _row(ORGANIZATION_FIELDS, attio_id="org-attio-1", name="Some Organization", **overrides)


@pytest.mark.parametrize("build", [build_seller_add_form_modal, build_buyer_add_form_modal])
@pytest.mark.parametrize("org", [None, _org_row()], ids=["new-org", "existing-org"])
def test_add_form_is_within_slack_limits(build, org):
    assert_valid_view(
        build(
            org=org,
            requested_by="U1",
            channel_id="C1",
            prefill_name="Acme",
            duplicate_candidates=["Acme Corp", "Acme Corporation"],
        ).to_dict()
    )


@pytest.mark.parametrize(
    ("build", "role_fields"),
    [
        (build_seller_edit_form_modal, SELLER_ROLE_FIELDS),
        (build_buyer_edit_form_modal, BUYER_ROLE_FIELDS),
    ],
)
def test_edit_form_is_within_slack_limits(build, role_fields):
    # The picker can select every field at once, so that is the worst case.
    assert_valid_view(
        build(
            _row(role_fields, id=uuid.uuid4(), organization=_org_row()),
            _org_row(),
            selected_org_fields=[f.name for f in ORGANIZATION_FIELDS],
            selected_role_fields=[f.name for f in role_fields],
            requested_by="U1",
            channel_id="C1",
        ).to_dict()
    )


def test_sector_focus_picker_renders_every_attio_option():
    """A wiring check, not a limit check: if `sector_focus` lost its options it
    would silently degrade to the free-text box that caused the original bug,
    and every other assertion here would still pass.
    """
    view = build_buyer_add_form_modal(org=None, requested_by="U1", channel_id="C1").to_dict()
    block = next(b for b in view["blocks"] if b.get("block_id") == "org_sector_focus")
    spec = next(f for f in ORGANIZATION_FIELDS if f.name == "sector_focus")
    assert block["element"]["type"] == "multi_static_select"
    assert [o["value"] for o in block["element"]["options"]] == list(spec.options)
