from ddl_commands.modules.slack.views.dynamic_fields import extract_field_value, render_field_block
from ddl_commands.shared.organization_field_spec import FieldSpec

# Was a "bool_as_text" spec until #53 made the column a real boolean. The
# tri-state Yes/No/Not-set rendering is what mattered and it is unchanged —
# only the stringify/parse round trip either side of it is gone.
_EARNOUT_SPEC = FieldSpec("earnout_tolerance", "Earnout tolerance", "bool")


def test_bool_renders_true_as_yes() -> None:
    block = render_field_block(_EARNOUT_SPEC, True)
    assert block["element"]["initial_option"]["value"] == "true"


def test_bool_renders_false_as_no() -> None:
    block = render_field_block(_EARNOUT_SPEC, False)
    assert block["element"]["initial_option"]["value"] == "false"


def test_bool_renders_none_as_not_set() -> None:
    """`False` and "never set" are different states and must stay distinguishable
    — a falsy check here would collapse them.
    """
    block = render_field_block(_EARNOUT_SPEC, None)
    assert block["element"]["initial_option"]["value"] == "unset"


def test_bool_extracts_a_real_bool_not_a_string() -> None:
    values = {"earnout_tolerance": {"earnout_tolerance": {"selected_option": {"value": "true"}}}}
    result = extract_field_value(_EARNOUT_SPEC, values)
    assert result is True
    assert isinstance(result, bool)


# `organizations.sector_focus` is `text[] NOT NULL DEFAULT '{}'` — the only
# `multi_select_text` field. Extraction used to return `None` for a blank
# box, which sailed through `OrganizationUpdate` (`list[str] | None`)
# untouched and hit Postgres's real NOT NULL constraint as the very last
# line of defense, after both an organization-fields Attio write and a role
# entry had already been created.
_SECTOR_FOCUS_SPEC = FieldSpec("sector_focus", "Sector focus", "multi_select_text")


def test_multi_select_text_renders_empty_list_as_blank() -> None:
    block = render_field_block(_SECTOR_FOCUS_SPEC, [])
    assert "initial_value" not in block["element"]


def test_multi_select_text_extracts_blank_as_empty_list_not_none() -> None:
    values = {"sector_focus": {"sector_focus": {"value": None}}}
    result = extract_field_value(_SECTOR_FOCUS_SPEC, values)
    assert result == []


def test_multi_select_text_extracts_comma_separated_values() -> None:
    values = {"sector_focus": {"sector_focus": {"value": "Fintech, Logistics"}}}
    result = extract_field_value(_SECTOR_FOCUS_SPEC, values)
    assert result == ["Fintech", "Logistics"]


# `organizations.twitter_follower_count` is `Integer` — the only `number`
# field — so, unlike `currency`'s reuse of the same Slack `number_input`
# block, decimals must not be offered and extraction must return a real
# `int`, not a `float`.
_FOLLOWER_COUNT_SPEC = FieldSpec("twitter_follower_count", "Twitter follower count", "number")


def test_number_renders_without_decimals_allowed() -> None:
    block = render_field_block(_FOLLOWER_COUNT_SPEC, 42)
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
