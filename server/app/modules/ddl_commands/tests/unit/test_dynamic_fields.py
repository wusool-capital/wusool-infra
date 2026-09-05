from app.modules.ddl_commands.api.schemas import FieldSpec
from app.modules.ddl_commands.api.slack.views.dynamic_fields import (
    extract_field_value,
    render_field_block,
)

# Was a "bool_as_text" spec until #53 made the column a real boolean. The
# tri-state Yes/No/Not-set rendering is what mattered and it is unchanged —
# only the stringify/parse round trip either side of it is gone.
_EARNOUT_SPEC = FieldSpec("earnout_tolerance", "Earnout tolerance", "bool")


def test_bool_renders_true_as_yes() -> None:
    block = render_field_block(_EARNOUT_SPEC, True).to_dict()
    assert block["element"]["initial_option"]["value"] == "true"


def test_bool_renders_false_as_no() -> None:
    block = render_field_block(_EARNOUT_SPEC, False).to_dict()
    assert block["element"]["initial_option"]["value"] == "false"


def test_bool_renders_none_as_not_set() -> None:
    """`False` and "never set" are different states and must stay distinguishable
    — a falsy check here would collapse them.
    """
    block = render_field_block(_EARNOUT_SPEC, None).to_dict()
    assert block["element"]["initial_option"]["value"] == "unset"


def test_bool_extracts_a_real_bool_not_a_string() -> None:
    values = {"earnout_tolerance": {"earnout_tolerance": {"selected_option": {"value": "true"}}}}
    result = extract_field_value(_EARNOUT_SPEC, values)
    assert result is True
    assert isinstance(result, bool)


# Both `multi_select_text` fields (`organizations.sector_focus`,
# `buyer_roles.target_geography`) are `text[] NOT NULL DEFAULT '{}'`.
# Extraction used to return `None` for a blank box, which sailed through
# `OrganizationUpdate` (`list[str] | None`) untouched and hit Postgres's real
# NOT NULL constraint as the very last line of defense, after both an
# organization-fields Attio write and a role entry had already been created.
# That invariant has to hold on both render paths below, so it is asserted
# on both.
#
# This spec carries no options on purpose: it pins the free-text fallback,
# which is still reachable for a stored value Attio no longer offers.
_SECTOR_FOCUS_SPEC = FieldSpec("sector_focus", "Sector focus", "multi_select_text")
_SECTOR_FOCUS_PICKER_SPEC = FieldSpec(
    "sector_focus", "Sector focus", "multi_select_text", options=("Fintech", "Logistics", "AI / ML")
)


def test_multi_select_text_renders_empty_list_as_blank() -> None:
    block = render_field_block(_SECTOR_FOCUS_SPEC, []).to_dict()
    assert "initial_value" not in block["element"]


def test_multi_select_text_extracts_blank_as_empty_list_not_none() -> None:
    values = {"sector_focus": {"sector_focus": {"value": None}}}
    result = extract_field_value(_SECTOR_FOCUS_SPEC, values)
    assert result == []


def test_multi_select_text_extracts_comma_separated_values() -> None:
    values = {"sector_focus": {"sector_focus": {"value": "Fintech, Logistics"}}}
    result = extract_field_value(_SECTOR_FOCUS_SPEC, values)
    assert result == ["Fintech", "Logistics"]


def test_multi_select_renders_a_picker_when_the_spec_has_options() -> None:
    block = render_field_block(_SECTOR_FOCUS_PICKER_SPEC, None).to_dict()
    assert block["element"]["type"] == "multi_static_select"
    assert [o["value"] for o in block["element"]["options"]] == [
        "Fintech",
        "Logistics",
        "AI / ML",
    ]
    # Nothing stored yet, so nothing pre-selected — Slack rejects an empty
    # `initial_options`, it has to be absent rather than `[]`.
    assert "initial_options" not in block["element"]


def test_multi_select_preselects_only_the_stored_values() -> None:
    block = render_field_block(_SECTOR_FOCUS_PICKER_SPEC, ["AI / ML", "Fintech"]).to_dict()
    assert [o["value"] for o in block["element"]["initial_options"]] == ["Fintech", "AI / ML"]


def test_multi_select_falls_back_to_free_text_for_a_value_not_in_the_options() -> None:
    """The picker cannot show a stored title Attio no longer offers, and Slack
    rejects an `initial_options` entry outside `options`. Dropping it from the
    pre-fill would silently discard it on the next save of any other field, so
    the whole block degrades to the free-text box instead.
    """
    block = render_field_block(
        _SECTOR_FOCUS_PICKER_SPEC, ["Fintech", "Quantum Computing"]
    ).to_dict()
    assert block["element"]["type"] == "plain_text_input"
    assert block["element"]["initial_value"] == "Fintech, Quantum Computing"
    assert block["label"]["text"] == "Sector focus (comma-separated)"


def test_multi_select_extracts_selected_options() -> None:
    values = {
        "sector_focus": {
            "sector_focus": {
                "type": "multi_static_select",
                "selected_options": [
                    {"text": {"type": "plain_text", "text": "Fintech"}, "value": "Fintech"},
                    {"text": {"type": "plain_text", "text": "AI / ML"}, "value": "AI / ML"},
                ],
            }
        }
    }
    assert extract_field_value(_SECTOR_FOCUS_PICKER_SPEC, values) == ["Fintech", "AI / ML"]


def test_multi_select_extracts_nothing_selected_as_empty_list_not_none() -> None:
    """`selected_options: []` is present-but-empty. Branching on truthiness
    would fall through to the comma-split path; the NOT NULL column needs
    `[]` either way.
    """
    values = {
        "sector_focus": {"sector_focus": {"type": "multi_static_select", "selected_options": []}}
    }
    assert extract_field_value(_SECTOR_FOCUS_PICKER_SPEC, values) == []


# `organizations.twitter_follower_count` is `Integer` — the only `number`
# field — so, unlike `currency`'s reuse of the same Slack `number_input`
# block, decimals must not be offered and extraction must return a real
# `int`, not a `float`.
_FOLLOWER_COUNT_SPEC = FieldSpec("twitter_follower_count", "Twitter follower count", "number")


def test_number_renders_without_decimals_allowed() -> None:
    block = render_field_block(_FOLLOWER_COUNT_SPEC, 42).to_dict()
    assert block["element"]["is_decimal_allowed"] is False
    assert block["element"]["initial_value"] == "42"


def test_number_extracts_a_real_int_not_a_float() -> None:
    values = {"twitter_follower_count": {"twitter_follower_count": {"value": "1200"}}}
    result = extract_field_value(_FOLLOWER_COUNT_SPEC, values)
    assert result == 1200
    assert isinstance(result, int)


def test_number_extracts_blank_as_none() -> None:
    values = {"twitter_follower_count": {"twitter_follower_count": {"value": ""}}}
    result = extract_field_value(_FOLLOWER_COUNT_SPEC, values)
    assert result is None


# `seller_roles.gross_margin_pct` is `Numeric` — a `percent` field, unlike
# `number`, must keep decimal precision (e.g. `12.5`), not truncate to `int`.
_GROSS_MARGIN_SPEC = FieldSpec("gross_margin_pct", "Gross margin %", "percent")


def test_percent_renders_with_decimals_allowed() -> None:
    block = render_field_block(_GROSS_MARGIN_SPEC, 12.5).to_dict()
    assert block["element"]["is_decimal_allowed"] is True
    assert block["element"]["initial_value"] == "12.5"


def test_percent_extracts_a_float_not_truncated_to_int() -> None:
    values = {"gross_margin_pct": {"gross_margin_pct": {"value": "12.5"}}}
    result = extract_field_value(_GROSS_MARGIN_SPEC, values)
    assert result == 12.5
    assert isinstance(result, float)


def test_percent_extracts_blank_as_none() -> None:
    values = {"gross_margin_pct": {"gross_margin_pct": {"value": ""}}}
    result = extract_field_value(_GROSS_MARGIN_SPEC, values)
    assert result is None
