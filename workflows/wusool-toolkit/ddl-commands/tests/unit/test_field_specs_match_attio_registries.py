"""A `FieldSpec` with kind `"date"`/`"currency"` also needs its own separate
entry in `attio.dates`/`attio.money`'s per-field registries — nothing else
catches a miss. A live `/add-buyer` hit `UnknownDateFieldError` for
`foundation_date` for exactly this reason before this test existed.
"""

from datetime import date

import pytest

from ddl_commands.modules.buyers.field_spec import BUYER_ROLE_FIELDS
from ddl_commands.modules.sellers.field_spec import SELLER_ROLE_FIELDS
from ddl_commands.shared.attio.dates import UnknownDateFieldError, serialize_date
from ddl_commands.shared.attio.money import UnknownMoneyFieldError, default_currency_code
from ddl_commands.shared.organization_field_spec import ORGANIZATION_FIELDS

# `money.py`'s registry keys role tables as "buyer_role"/"seller_role"
# (singular) — matches `build_attio_values`'s own `table` argument, not the
# plural Postgres table names.
_TABLES = [
    ("organizations", ORGANIZATION_FIELDS),
    ("buyer_role", BUYER_ROLE_FIELDS),
    ("seller_role", SELLER_ROLE_FIELDS),
]


@pytest.mark.parametrize(("table", "fields"), _TABLES, ids=[t for t, _ in _TABLES])
def test_every_date_field_is_registered(table, fields) -> None:
    unregistered = []
    for spec in fields:
        if spec.kind != "date":
            continue
        try:
            serialize_date(spec.name, date(2026, 1, 1))
        except UnknownDateFieldError as exc:
            unregistered.append(f"{spec.name}: {exc}")
    assert not unregistered, f"{table}: {unregistered}"


@pytest.mark.parametrize(("table", "fields"), _TABLES, ids=[t for t, _ in _TABLES])
def test_every_currency_field_is_registered(table, fields) -> None:
    unregistered = []
    for spec in fields:
        if spec.kind != "currency":
            continue
        try:
            default_currency_code(table, spec.name)
        except UnknownMoneyFieldError as exc:
            unregistered.append(f"{spec.name}: {exc}")
    assert not unregistered, f"{table}: {unregistered}"
