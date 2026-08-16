from ddl_commands.modules.slack.views.dynamic_fields import extract_field_value, render_field_block
from ddl_commands.shared.organization_field_spec import FieldSpec

_EARNOUT_SPEC = FieldSpec("earnout_tolerance", "Earnout tolerance", "bool_as_text")


def test_bool_as_text_renders_true_string_as_yes() -> None:
    block = render_field_block(_EARNOUT_SPEC, "true")
    assert block["element"]["initial_option"]["value"] == "true"


def test_bool_as_text_renders_false_string_as_no() -> None:
    block = render_field_block(_EARNOUT_SPEC, "false")
    assert block["element"]["initial_option"]["value"] == "false"


def test_bool_as_text_renders_none_as_not_set() -> None:
    block = render_field_block(_EARNOUT_SPEC, None)
    assert block["element"]["initial_option"]["value"] == "unset"


def test_bool_as_text_renders_unrecognized_string_as_false() -> None:
    """Matches `database/sync-postgres.ps1`'s own `boolean()` fallback: only
    a genuinely absent value (`None`) is "not set" — any stored string that
    isn't one of the truthy tokens is treated as false, same as the sync
    script would read it. In practice the column only ever holds `NULL`,
    `"true"`, or `"false"` (this bot only ever writes those two strings —
    see `write_payload.build_postgres_values`), so this is a defensive
    fallback, not a real data case.
    """
    block = render_field_block(_EARNOUT_SPEC, "maybe")
    assert block["element"]["initial_option"]["value"] == "false"


def test_bool_as_text_extracts_a_real_bool_not_a_string() -> None:
    values = {
        "earnout_tolerance": {
            "earnout_tolerance": {"selected_option": {"value": "true"}}
        }
    }
    result = extract_field_value(_EARNOUT_SPEC, values)
    assert result is True
    assert isinstance(result, bool)
