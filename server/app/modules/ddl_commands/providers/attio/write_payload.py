"""Converts extracted field values (already in Postgres's own shape — see
`dynamic_fields.extract_field_value`) into Attio's write shape for the same
fields: resolving select titles to live option IDs, applying the field's
fixed currency code, formatting dates. This is the one place both writes
(Attio and Postgres) are guaranteed to have started from the same value —
Postgres writes the *extracted* value directly, Attio writes this
function's output of it.

Select/multiselect values are always an array in Attio's API, even for a
single value, and a resolved option ID must be wrapped as `{"option": id}`
— confirmed against Attio's own REST API docs
(rest-api/attribute-types/attribute-types-select), not inferred. Every
other kind (text, date, currency, bool, number, percent) is a bare value,
unwrapped.
"""

from collections.abc import Mapping
from typing import cast

from app.modules.attio import AttioClientProtocol
from app.modules.attio.providers.attio.dates import serialize_date
from app.modules.attio.providers.attio.money import serialize_money, to_postgres_money
from app.modules.attio.providers.attio.options import get_option_id
from app.modules.ddl_commands.api.schemas import FieldSpec, PrefillValue
from app.modules.utilities.domain.json_types import JsonObject


def build_postgres_values(
    *, table: str, fields: dict[str, FieldSpec], extracted: Mapping[str, PrefillValue | None]
) -> dict[str, PrefillValue | None]:
    """One kind needs reshaping from what `dynamic_fields.extract_field_value`
    returns: `currency` (a bare amount -> `MoneyJson`, itself a `dict` and so
    a `PrefillValue`'s `JsonObject` member's own shape). Every other kind is
    already stored in Postgres exactly as extracted. `extracted` is
    genuinely `dict[str, PrefillValue | None]` at every real call site
    (`extract_field_value`'s own return shape) — not the arbitrary
    `JsonObject` this used to widen it to.
    """
    postgres_values: dict[str, PrefillValue | None] = {}
    for name, value in extracted.items():
        spec = fields[name]
        # `isinstance`, not `value is not None`: `extract_field_value` only
        # ever returns a bare `float` for `currency`, but narrowing this way
        # (matching `wrap_prefill_value`'s own check) is what lets
        # `to_postgres_money`'s `amount: float` param type-check without a
        # `cast`.
        if spec.kind == "currency" and isinstance(value, (int, float)):
            # `MoneyJson` (a `TypedDict`) is a real `dict` at runtime — the
            # cast only tells the type checker what `isinstance` already
            # guarantees at the call above, matching `wrap_prefill_value`'s
            # own currency wrap.
            postgres_values[name] = cast(JsonObject, to_postgres_money(table, name, value))
        else:
            postgres_values[name] = value
    return postgres_values


async def build_attio_values(
    client: AttioClientProtocol,
    *,
    target_kind: str,
    target_slug: str,
    table: str,
    fields: dict[str, FieldSpec],
    extracted: JsonObject,
) -> JsonObject:
    """`fields` maps field name -> its `FieldSpec` (so kind/options are
    known); `extracted` maps field name -> the value already extracted from
    Slack, in Postgres's shape. Returns Attio's `values`/`entry_values`
    payload body (attribute slug -> Attio value) for exactly the fields
    present in `extracted`.

    `extracted` stays the generic `JsonObject`, not `dict[str, PrefillValue]`
    (contrast `build_postgres_values` above): every branch below dispatches
    on `spec.kind` — a runtime string, not something a type checker can
    narrow a union against — and each already knows its own real type
    without needing (or being able to use) a static discriminant, the same
    reasoning `render_field_block`'s own docstring gives for staying `Any`.
    """
    attio_values: JsonObject = {}
    for name, value in extracted.items():
        if value is None:
            continue
        spec = fields[name]
        if spec.kind in ("text", "multiline", "multi_select_as_text", "text_list"):
            # `text_list` sends a bare `list[str]` unchanged — unlike
            # `multi_select_text` below, `domains` (its only field today) is
            # a plain Attio `text` attribute taking multiple raw strings
            # (verified live: `attribute["type"] == "text"`, not a select),
            # so there is no option ID to resolve.
            attio_values[name] = value
        elif spec.kind == "select":
            option_id = await get_option_id(
                client,
                target_kind=target_kind,
                target_slug=target_slug,
                attribute_slug=name,
                title=value,
            )
            # Attio select/multiselect values are always an array, even for
            # a single value, and an ID must be wrapped as {"option": id} —
            # confirmed against Attio's own docs (attribute-types-select),
            # not just this codebase's own earlier PATCH precedent, which
            # (incorrectly) sent a bare, unwrapped ID.
            attio_values[name] = [{"option": option_id}]
        elif spec.kind == "multi_select_text":
            attio_values[name] = [
                {
                    "option": await get_option_id(
                        client,
                        target_kind=target_kind,
                        target_slug=target_slug,
                        attribute_slug=name,
                        title=title,
                    )
                }
                for title in value
            ]
        elif spec.kind == "date":
            attio_values[name] = serialize_date(name, value)
        elif spec.kind == "currency":
            attio_values[name] = serialize_money(table, name, value)
        elif spec.kind == "bool":
            attio_values[name] = value
        elif spec.kind == "number":
            attio_values[name] = value
        elif spec.kind == "percent":
            attio_values[name] = value
        else:
            raise ValueError(f"Unsupported field kind for Attio write: {spec.kind!r}")
    return attio_values
