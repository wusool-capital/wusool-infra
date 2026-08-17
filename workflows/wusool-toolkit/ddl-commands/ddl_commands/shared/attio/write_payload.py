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
other kind (text, date, currency, bool) is a bare value, unwrapped.
"""

from ddl_commands.shared.attio.client import AttioClient
from ddl_commands.shared.attio.dates import serialize_date
from ddl_commands.shared.attio.money import serialize_money, to_postgres_money
from ddl_commands.shared.attio.options import get_option_id
from ddl_commands.shared.organization_field_spec import FieldSpec


def build_postgres_values(
    *, table: str, fields: dict[str, FieldSpec], extracted: dict
) -> dict:
    """Two kinds need reshaping from what `dynamic_fields.extract_field_value`
    returns: `currency` (a bare amount -> `{"amount", "currency"}`) and
    `bool_as_text` (a real `bool` -> the `"true"`/`"false"` string Postgres's
    `text` column actually holds for `earnout_tolerance` — see
    `organization_field_spec.py`'s `FieldKind` docstring for why that column
    is text at all). Every other kind is already stored in Postgres exactly
    as extracted.
    """
    postgres_values: dict = {}
    for name, value in extracted.items():
        spec = fields[name]
        if spec.kind == "currency" and value is not None:
            postgres_values[name] = to_postgres_money(table, name, value)
        elif spec.kind == "bool_as_text" and value is not None:
            postgres_values[name] = "true" if value else "false"
        else:
            postgres_values[name] = value
    return postgres_values


async def build_attio_values(
    client: AttioClient,
    *,
    target_kind: str,
    target_slug: str,
    table: str,
    fields: dict[str, FieldSpec],
    extracted: dict,
) -> dict:
    """`fields` maps field name -> its `FieldSpec` (so kind/options are
    known); `extracted` maps field name -> the value already extracted from
    Slack, in Postgres's shape. Returns Attio's `values`/`entry_values`
    payload body (attribute slug -> Attio value) for exactly the fields
    present in `extracted`.
    """
    attio_values: dict = {}
    for name, value in extracted.items():
        if value is None:
            continue
        spec = fields[name]
        if spec.kind in ("text", "multiline"):
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
        elif spec.kind in ("bool", "bool_as_text"):
            attio_values[name] = value
        else:
            raise ValueError(f"Unsupported field kind for Attio write: {spec.kind!r}")
    return attio_values
