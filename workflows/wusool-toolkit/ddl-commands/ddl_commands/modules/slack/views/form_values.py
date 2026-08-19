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


def text_input_block(
    field: str, label: str, value: str | None, *, multiline: bool = False
) -> dict:
    element: dict = {"type": "plain_text_input", "action_id": field}
    if multiline:
        element["multiline"] = True
    if value:
        element["initial_value"] = value
    return {
        "type": "input",
        "block_id": field,
        "optional": True,
        "label": {"type": "plain_text", "text": label},
        "element": element,
    }


def number_input_block(field: str, label: str, value: float | None) -> dict:
    element: dict = {"type": "number_input", "action_id": field, "is_decimal_allowed": True}
    if value is not None:
        element["initial_value"] = str(value)
    return {
        "type": "input",
        "block_id": field,
        "optional": True,
        "label": {"type": "plain_text", "text": label},
        "element": element,
    }


def date_input_block(field: str, label: str, value: date | None) -> dict:
    element: dict = {"type": "datepicker", "action_id": field}
    if value:
        element["initial_date"] = value.isoformat()
    return {
        "type": "input",
        "block_id": field,
        "optional": True,
        "label": {"type": "plain_text", "text": label},
        "element": element,
    }


def bool_select_block(field: str, label: str, value: bool | None) -> dict:
    """A tri-state Yes/No/Not-set select — a checkbox can't represent "unset"
    distinctly from "false", but this field is a real `bool | None` column.
    """
    options = [
        {"text": {"type": "plain_text", "text": "Yes"}, "value": "true"},
        {"text": {"type": "plain_text", "text": "No"}, "value": "false"},
        {"text": {"type": "plain_text", "text": "Not set"}, "value": "unset"},
    ]
    initial_value = "true" if value is True else "false" if value is False else "unset"
    initial_option = next(o for o in options if o["value"] == initial_value)
    return {
        "type": "input",
        "block_id": field,
        "optional": True,
        "label": {"type": "plain_text", "text": label},
        "element": {
            "type": "static_select",
            "action_id": field,
            "options": options,
            "initial_option": initial_option,
        },
    }


def money_input_blocks(field: str, label: str, money: dict | None) -> list[dict]:
    amount = money.get("amount") if money else None
    currency = money.get("currency") if money else None
    return [
        number_input_block(f"{field}_amount", f"{label} — amount", amount),
        text_input_block(f"{field}_currency", f"{label} — currency (e.g. AED)", currency),
    ]


def select_block(field: str, label: str, value: str | None, options: tuple[str, ...]) -> dict:
    """A plain single-select — unlike `bool_select_block`, options come from
    the caller's own fixed vocabulary (`FieldSpec.options`), not a hardcoded
    tri-state. `optional=True` so leaving it unset doesn't block the form —
    Slack requires an `initial_option` be one of `options`, so only set one
    when the current value actually matches; otherwise the picker opens
    blank rather than silently defaulting to the first option.
    """
    slack_options = [{"text": {"type": "plain_text", "text": o}, "value": o} for o in options]
    element: dict = {"type": "static_select", "action_id": field, "options": slack_options}
    if value in options:
        element["initial_option"] = next(o for o in slack_options if o["value"] == value)
    return {
        "type": "input",
        "block_id": field,
        "optional": True,
        "label": {"type": "plain_text", "text": label},
        "element": element,
    }


def multi_select_text_block(field: str, label: str, values: list[str] | None) -> dict:
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
) -> dict:
    """A required checkbox, not just a relabeled submit button, so the
    gated action is something the operator must actively opt into. Nothing
    is gated today — `intake_source` was the only such field and #53 dropped
    it — but `GATED_*_ROLE_FIELDS` still drives this for the next one.
    """
    return {
        "type": "input",
        "block_id": block_id,
        "label": {"type": "plain_text", "text": label},
        "element": {
            "type": "checkboxes",
            "action_id": action_id,
            "options": [{"text": {"type": "plain_text", "text": option_text}, "value": "confirm"}],
        },
    }


def get_text(values: dict, block_id: str, action_id: str) -> str | None:
    raw = values.get(block_id, {}).get(action_id, {}).get("value")
    return raw if raw else None


def get_number(values: dict, block_id: str, action_id: str) -> float | None:
    raw = values.get(block_id, {}).get(action_id, {}).get("value")
    if not raw:
        return None
    try:
        return float(raw)
    except ValueError:
        return None


def get_date(values: dict, block_id: str, action_id: str) -> str | None:
    return values.get(block_id, {}).get(action_id, {}).get("selected_date")


def get_static_select(values: dict, block_id: str, action_id: str) -> str | None:
    option = values.get(block_id, {}).get(action_id, {}).get("selected_option")
    return option["value"] if option else None


def get_bool_select(values: dict, block_id: str, action_id: str) -> bool | None:
    raw = get_static_select(values, block_id, action_id)
    if raw == "true":
        return True
    if raw == "false":
        return False
    return None


def get_checkbox_selected(values: dict, block_id: str, action_id: str) -> bool:
    options = values.get(block_id, {}).get(action_id, {}).get("selected_options") or []
    return len(options) > 0


def extract_money(values: dict, field: str) -> dict | None:
    amount = get_number(values, f"{field}_amount", f"{field}_amount")
    currency = get_text(values, f"{field}_currency", f"{field}_currency")
    if amount is None and currency is None:
        return None
    return {"amount": amount, "currency": currency}


def pydantic_errors_to_slack(errors: list[dict]) -> dict[str, str]:
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
