"""Coverage for `build_seller_add_form_modal`'s `prefill` parameter — the
seam `discovery`'s hand-off relies on. `render_field_block`/
`extract_field_value` themselves are already covered in
`test_dynamic_fields.py`; this covers the wiring specific to prefill:
does a prefilled value actually reach the right block, and does an
out-of-vocabulary value get silently dropped rather than corrupting the
rendered form.
"""

from app.modules.ddl_commands.api.slack.views.dynamic_fields import extract_field_value
from app.modules.ddl_commands.api.slack.views.seller_add_form import build_seller_add_form_modal


def _block(view, block_id: str) -> dict:
    return next(b.to_dict() for b in view.blocks if b.block_id == block_id)


def test_prefill_populates_a_role_text_currency_field() -> None:
    view = build_seller_add_form_modal(
        org=None,
        requested_by="U1",
        channel_id="C1",
        prefill_name="Acme Co",
        prefill={"est_revenue": 5_000_000.0},
    )

    block = _block(view, "est_revenue")
    assert block["element"]["initial_value"] == "5000000.0"


def test_prefill_populates_an_org_field_with_the_org_block_prefix() -> None:
    view = build_seller_add_form_modal(
        org=None,
        requested_by="U1",
        channel_id="C1",
        prefill_name="Acme Co",
        prefill={"hq_country": "United Arab Emirates"},
    )

    block = _block(view, "org_hq_country")
    assert [o["value"] for o in block["element"]["initial_options"]] == ["United Arab Emirates"]


def test_prefill_matching_select_option_sets_initial_option() -> None:
    view = build_seller_add_form_modal(
        org=None,
        requested_by="U1",
        channel_id="C1",
        prefill_name="Acme Co",
        prefill={"employee_range": "11-50"},
    )

    block = _block(view, "org_employee_range")
    assert block["element"]["initial_option"]["value"] == "11-50"


def test_prefill_value_outside_vocabulary_leaves_select_unset() -> None:
    """`render_field_block`'s own behavior for an out-of-vocabulary select
    value — no `initial_option` at all, never a fabricated match — this
    just confirms the add-form's prefill wiring doesn't short-circuit it.
    """
    view = build_seller_add_form_modal(
        org=None,
        requested_by="U1",
        channel_id="C1",
        prefill_name="Acme Co",
        prefill={"employee_range": "not a real band"},
    )

    block = _block(view, "org_employee_range")
    # slack-sdk's `to_dict()` omits a `None`-valued key entirely rather
    # than emitting `"initial_option": null`.
    assert "initial_option" not in block["element"]


def test_prefill_round_trips_through_extraction() -> None:
    """The full loop: a prefilled value renders as a Slack initial value,
    and — simulating an operator submitting the form untouched — the same
    shape extracts back out to the value that was prefilled.
    """
    from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME

    view = build_seller_add_form_modal(
        org=None,
        requested_by="U1",
        channel_id="C1",
        prefill_name="Acme Co",
        prefill={"hq_country": "United Arab Emirates"},
    )
    block = _block(view, "org_hq_country")
    selected = [{"value": o["value"]} for o in block["element"]["initial_options"]]

    values = {"org_hq_country": {"org_hq_country": {"selected_options": selected}}}
    extracted = extract_field_value(
        ORGANIZATION_FIELDS_BY_NAME["hq_country"], values, block_id_prefix="org_"
    )

    assert extracted == "United Arab Emirates"


def test_no_prefill_leaves_role_fields_blank() -> None:
    view = build_seller_add_form_modal(
        org=None, requested_by="U1", channel_id="C1", prefill_name="Acme Co"
    )

    block = _block(view, "est_revenue")
    assert "initial_value" not in block["element"]
