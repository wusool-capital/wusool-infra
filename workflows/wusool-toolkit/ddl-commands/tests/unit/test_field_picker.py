from ddl_commands.modules.buyers.field_spec import BUYER_ROLE_FIELDS
from ddl_commands.modules.sellers.field_spec import SELLER_ROLE_FIELDS
from ddl_commands.modules.slack.views.field_picker import (
    build_field_picker_modal,
    wants_key_contact,
)


def _base_kwargs(kind: str, role_fields) -> dict:
    return {
        "kind": kind,
        "role_id": "role-1",
        "org_name": "Some Org",
        "requested_by": "U1",
        "channel_id": "C1",
        "role_fields": role_fields,
    }


def test_seller_field_picker_has_no_key_contact_block() -> None:
    """Sellers have no key contact — the block shouldn't exist at all, not
    just be absent from what the operator picks.
    """
    view = build_field_picker_modal(**_base_kwargs("seller", SELLER_ROLE_FIELDS))
    block_ids = [b.get("block_id") for b in view["blocks"]]
    assert "key_contact_flag" not in block_ids


def test_buyer_field_picker_has_key_contact_block() -> None:
    view = build_field_picker_modal(**_base_kwargs("buyer", BUYER_ROLE_FIELDS))
    block_ids = [b.get("block_id") for b in view["blocks"]]
    assert "key_contact_flag" in block_ids


def test_wants_key_contact_true_when_checked() -> None:
    values = {
        "key_contact_flag": {
            "set_key_contact": {
                "selected_options": [{"value": "set_key_contact"}],
            }
        }
    }
    assert wants_key_contact(values) is True


def test_wants_key_contact_false_when_unchecked() -> None:
    values = {"key_contact_flag": {"set_key_contact": {"selected_options": []}}}
    assert wants_key_contact(values) is False


def test_wants_key_contact_false_when_block_missing() -> None:
    """The seller field-picker never renders this block at all — reading it
    from a payload that lacks it must not raise.
    """
    assert wants_key_contact({}) is False
