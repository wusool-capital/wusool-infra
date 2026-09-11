"""Renders/extracts a Slack `input` block for one `FieldSpec`, regardless of
which table it belongs to — the field-picker's selection drives which of
these actually appear in a given form. `block_id_prefix` exists for one
reason: `organizations.relationship_status` and `seller_roles.relationship_status`
are two different attributes with two different vocabularies that happen to
share a column name — org fields get an `"org_"` block_id prefix so a form
that shows both can never collide.
"""

from datetime import date
from typing import Any

from slack_sdk.models.blocks import InputBlock

from app.modules.ddl_commands.api.schemas import FieldSpec, PrefillValue
from app.modules.ddl_commands.api.slack.views.form_values import (
    bool_select_block,
    date_input_block,
    get_bool_select,
    get_date,
    get_multi_static_select,
    get_number,
    get_static_select,
    get_text,
    multi_select_block,
    number_input_block,
    select_block,
    text_input_block,
)
from app.modules.utilities.domain.json_types import JsonObject


def _block_id(spec: FieldSpec, block_id_prefix: str) -> str:
    return f"{block_id_prefix}{spec.name}"


def render_field_block(
    spec: FieldSpec, current_value: Any, *, block_id_prefix: str = ""
) -> InputBlock:
    """`current_value` is a `PrefillValue | None` in shape, but stays `Any`
    here on purpose: this function dispatches on `spec.kind` — a runtime
    string, not something a type checker can narrow a union against — so
    each per-kind branch below already knows its own real type without
    needing (or being able to use) a static discriminant.
    """
    block_id = _block_id(spec, block_id_prefix)
    if spec.kind == "text":
        return text_input_block(block_id, spec.label, current_value)
    if spec.kind == "multiline":
        return text_input_block(block_id, spec.label, current_value, multiline=True)
    if spec.kind == "select":
        return select_block(block_id, spec.label, current_value, spec.options)
    if spec.kind == "multi_select_text":
        return multi_select_block(block_id, spec.label, current_value, spec.options)
    if spec.kind == "multi_select_as_text":
        selected = [part.strip() for part in current_value.split(",")] if current_value else []
        return multi_select_block(block_id, spec.label, selected, spec.options)
    if spec.kind == "date":
        return date_input_block(block_id, spec.label, current_value)
    if spec.kind == "currency":
        amount = current_value.get("amount") if current_value else None
        return number_input_block(block_id, spec.label, amount)
    if spec.kind == "bool":
        return bool_select_block(block_id, spec.label, current_value)
    if spec.kind == "number":
        return number_input_block(block_id, spec.label, current_value, is_decimal_allowed=False)
    if spec.kind == "percent":
        return number_input_block(block_id, spec.label, current_value, is_decimal_allowed=True)
    raise ValueError(f"Unsupported field kind for rendering: {spec.kind!r}")


def extract_field_value(
    spec: FieldSpec, values: JsonObject, *, block_id_prefix: str = ""
) -> PrefillValue | None:
    """Returns a plain value in the same shape Postgres already stores
    (title strings for selects, a bare `float | None` amount for money — the
    caller wraps it with `{"amount": ..., "currency": ...}` once it knows
    which table the field belongs to, via
    `app.modules.attio.providers.attio.money.default_currency_code`, so both the
    Postgres write and the Attio write use the identical fixed currency — a
    `list[str]` for the multi-select stand-in). Attio-specific serialization
    beyond that (option IDs, date-vs-timestamp shape) happens later, only
    when actually building the Attio write payload.
    """
    block_id = _block_id(spec, block_id_prefix)
    if spec.kind in ("text", "multiline"):
        return get_text(values, block_id, block_id)
    if spec.kind == "select":
        return get_static_select(values, block_id, block_id)
    if spec.kind == "multi_select_text":
        # Both columns are `text[] NOT NULL`, so a blank field must extract to
        # `[]`, never `None`. Tested on presence rather than truthiness because
        # an empty multi-select sends `selected_options: []`, which would
        # otherwise fall through to the free-text branch.
        state = values.get(block_id, {}).get(block_id, {})
        if "selected_options" in state:
            return get_multi_static_select(values, block_id, block_id)
        raw = get_text(values, block_id, block_id)
        if not raw:
            return []
        return [part.strip() for part in raw.split(",") if part.strip()]
    if spec.kind == "multi_select_as_text":
        # The column is nullable text, so nothing picked is NULL, not "".
        return ", ".join(get_multi_static_select(values, block_id, block_id)) or None
    if spec.kind == "date":
        raw = get_date(values, block_id, block_id)
        return date.fromisoformat(raw) if raw else None
    if spec.kind == "currency":
        raw = values.get(block_id, {}).get(block_id, {}).get("value")
        if not raw:
            return None
        try:
            return float(raw)
        except ValueError:
            return None
    if spec.kind == "bool":
        return get_bool_select(values, block_id, block_id)
    if spec.kind == "number":
        raw = get_number(values, block_id, block_id)
        return int(raw) if raw is not None else None
    if spec.kind == "percent":
        return get_number(values, block_id, block_id)
    raise ValueError(f"Unsupported field kind for extraction: {spec.kind!r}")


def wrap_prefill_value(spec: FieldSpec, value: PrefillValue | None) -> Any:
    """Shapes a raw prefill value (`discovery`'s draft, `enrichment`'s
    proposal) the way `render_field_block` expects for `spec.kind` —
    doesn't decide *whether* to use it over a current value, only how to
    shape it once a caller has already decided to. Returns `Any`, not
    `PrefillValue`, since its one job is producing exactly what
    `render_field_block`'s dynamic dispatch wants — see that function's
    own docstring for why that boundary stays untyped.

    `render_field_block`'s `currency` branch expects the same
    `{"amount": ...}` shape an existing role's ORM column already carries
    — a prefill source instead supplies a bare amount, matching
    `extract_field_value`'s own output shape, so it is wrapped here rather
    than at every caller.
    """
    if spec.kind == "currency" and isinstance(value, (int, float)):
        return {"amount": value}
    return value


def normalize_prefill(
    values: dict[str, PrefillValue], fields_by_name: dict[str, FieldSpec]
) -> dict[str, PrefillValue]:
    """Drops any value not in a `select`/`multi_select_text` field's fixed
    vocabulary (never passed through as free text) — Slack silently drops an
    unmatched `select` initial_option and degrades `multi_select_text` to a
    free-text box (see `render_field_block`), so normalizing before prefill
    keeps the rendered form predictable either way. Shared by every prefill
    source (`discovery`'s draft, `enrichment`'s proposal) — previously two
    near-identical private copies, one per adapter.
    """
    normalized: dict[str, PrefillValue] = {}
    for name, value in values.items():
        spec = fields_by_name.get(name)
        if spec is None or value is None:
            continue
        if spec.kind == "select" and value not in spec.options:
            continue
        if spec.kind == "multi_select_text":
            kept = [v for v in value if v in spec.options] if isinstance(value, list) else []
            if not kept:
                continue
            normalized[name] = kept
            continue
        normalized[name] = value
    return normalized
