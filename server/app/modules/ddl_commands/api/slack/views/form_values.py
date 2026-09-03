"""Shared Block Kit `input`-block builders and `view["state"]["values"]`
extraction helpers, used by every seller/buyer edit form instead of
duplicating parsing per-view.

Block-id convention: a scalar field's block_id is the field name itself
(e.g. `"sell_timeline"`); a money field splits into two blocks,
`"<field>_amount"` and `"<field>_currency"`. This convention is what lets
`pydantic_errors_to_slack` map a Pydantic `error["loc"]` tuple straight back
to a block_id with no lookup table — `("est_revenue", "currency")` becomes
`"est_revenue_currency"` automatically.
"""

from datetime import date
from typing import Any

from pydantic_core import ErrorDetails
from slack_sdk.models.blocks import InputBlock
from slack_sdk.models.blocks.basic_components import Option
from slack_sdk.models.blocks.block_elements import (
    CheckboxesElement,
    DatePickerElement,
    NumberInputElement,
    PlainTextInputElement,
    StaticSelectElement,
)


def text_input_block(
    field: str, label: str, value: str | None, *, multiline: bool = False
) -> InputBlock:
    return InputBlock(
        block_id=field,
        optional=True,
        label=label,
        element=PlainTextInputElement(
            action_id=field, multiline=multiline or None, initial_value=value or None
        ),
    )


def number_input_block(
    field: str, label: str, value: float | None, *, is_decimal_allowed: bool = True
) -> InputBlock:
    return InputBlock(
        block_id=field,
        optional=True,
        label=label,
        element=NumberInputElement(
            action_id=field,
            is_decimal_allowed=is_decimal_allowed,
            initial_value=str(value) if value is not None else None,
        ),
    )


def date_input_block(field: str, label: str, value: date | None) -> InputBlock:
    return InputBlock(
        block_id=field,
        optional=True,
        label=label,
        element=DatePickerElement(
            action_id=field, initial_date=value.isoformat() if value else None
        ),
    )


def bool_select_block(field: str, label: str, value: bool | None) -> InputBlock:
    """A tri-state Yes/No/Not-set select — a checkbox can't represent "unset"
    distinctly from "false", but this field is a real `bool | None` column.
    """
    options = [Option(label="Yes", value="true"), Option(label="No", value="false"),
               Option(label="Not set", value="unset")]
    initial_value = "true" if value is True else "false" if value is False else "unset"
    initial_option = next(o for o in options if o.value == initial_value)
    return InputBlock(
        block_id=field,
        optional=True,
        label=label,
        element=StaticSelectElement(
            action_id=field, options=options, initial_option=initial_option
        ),
    )


def select_block(field: str, label: str, value: str | None, options: tuple[str, ...]) -> InputBlock:
    """A plain single-select — unlike `bool_select_block`, options come from
    the caller's own fixed vocabulary (`FieldSpec.options`), not a hardcoded
    tri-state. `optional=True` so leaving it unset doesn't block the form —
    Slack requires an `initial_option` be one of `options`, so only set one
    when the current value actually matches; otherwise the picker opens
    blank rather than silently defaulting to the first option.
    """
    slack_options = [Option(label=o, value=o) for o in options]
    initial_option = next((o for o in slack_options if o.value == value), None)
    return InputBlock(
        block_id=field,
        optional=True,
        label=label,
        element=StaticSelectElement(
            action_id=field, options=slack_options, initial_option=initial_option
        ),
    )


def multi_select_text_block(field: str, label: str, values: list[str] | None) -> InputBlock:
    """Free-text, comma-separated stand-in for a true Slack multi-select —
    each typed title is resolved against Attio's live option list on
    submit (same principle as `select_block`'s single-select options: never
    hardcode a picker that can silently drift from Attio's real option set,
    and Slack's own `multi_static_select` still requires the full option
    list to be known ahead of render time, same constraint this avoids).
    """
    initial = ", ".join(values) if values else None
    return text_input_block(field, label, initial)


def confirmation_checkbox_block(
    block_id: str, action_id: str, label: str, option_text: str
) -> InputBlock:
    """A required checkbox, not just a relabeled submit button, so the
    gated action is something the operator must actively opt into. Nothing
    is gated today — `intake_source` was the only such field and #53 dropped
    it — but `GATED_*_ROLE_FIELDS` still drives this for the next one.
    """
    return InputBlock(
        block_id=block_id,
        label=label,
        element=CheckboxesElement(
            action_id=action_id, options=[Option(label=option_text, value="confirm")]
        ),
    )


def get_text(values: dict[str, Any], block_id: str, action_id: str) -> str | None:
    raw = values.get(block_id, {}).get(action_id, {}).get("value")
    return raw if raw else None


def get_number(values: dict[str, Any], block_id: str, action_id: str) -> float | None:
    raw = values.get(block_id, {}).get(action_id, {}).get("value")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_date(values: dict[str, Any], block_id: str, action_id: str) -> str | None:
    return values.get(block_id, {}).get(action_id, {}).get("selected_date")


def get_static_select(values: dict[str, Any], block_id: str, action_id: str) -> str | None:
    option = values.get(block_id, {}).get(action_id, {}).get("selected_option")
    return option["value"] if option else None


def get_bool_select(values: dict[str, Any], block_id: str, action_id: str) -> bool | None:
    raw = get_static_select(values, block_id, action_id)
    if raw == "true":
        return True
    if raw == "false":
        return False
    return None


def get_checkbox_selected(values: dict[str, Any], block_id: str, action_id: str) -> bool:
    options = values.get(block_id, {}).get(action_id, {}).get("selected_options") or []
    return len(options) > 0


def pydantic_errors_to_slack(errors: list[ErrorDetails]) -> dict[str, str]:
    """Maps every Pydantic `ValidationError.errors()` entry to a block_id via
    the naming convention above — collects ALL errors, not just the first,
    so a single `ack(response_action="errors", errors={...})` call can
    surface every invalid field at once (Slack's own constraint: one round
    trip, all errors together).
    """
    result: dict[str, str] = {}
    for err in errors:
        loc = err["loc"]
        block_id = "_".join(str(part) for part in loc) if loc else "form"
        result[block_id] = err["msg"]
    return result
