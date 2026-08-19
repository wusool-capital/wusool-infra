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
