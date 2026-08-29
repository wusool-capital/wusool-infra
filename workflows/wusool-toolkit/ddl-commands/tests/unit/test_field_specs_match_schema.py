"""Every editable field must still exist on the table, with a compatible type.

The rest of the suite builds roles out of `SimpleNamespace` stubs, so it
stayed green through #53 dropping `seller_roles.intake_source` and retyping
`buyer_roles.earnout_tolerance` from text to boolean — both of which the bot
was still writing. This is the one place that reads the real SQLAlchemy
columns, so a schema change lands as a failing test rather than a runtime
error on someone's `/add-seller`.
"""

import pytest
from sqlalchemy import ARRAY, Boolean, Date, Integer, Numeric, Text
from sqlalchemy.dialects.postgresql import JSONB
from wusool_db.models import BuyerRole, Organization, SellerRole

from ddl_commands.modules.buyers.field_spec import BUYER_ROLE_FIELDS
from ddl_commands.modules.sellers.field_spec import SELLER_ROLE_FIELDS
from ddl_commands.shared.organization_field_spec import ORGANIZATION_FIELDS

_SPECS = [
    pytest.param(Organization, ORGANIZATION_FIELDS, id="organizations"),
    pytest.param(SellerRole, SELLER_ROLE_FIELDS, id="seller_roles"),
    pytest.param(BuyerRole, BUYER_ROLE_FIELDS, id="buyer_roles"),
]

# What each FieldSpec kind reads from and writes to Postgres. `select` is an
# Attio option title stored as text, `multi_select_text` a text array of them;
# `currency` is the `{"amount", "currency"}` JSONB shape.
_EXPECTED_COLUMN_TYPE = {
    "text": Text,
    "multiline": Text,
    "select": Text,
    "multi_select_text": ARRAY,
    "currency": JSONB,
    "date": Date,
    "bool": Boolean,
    "number": Integer,
    "percent": Numeric,
}


@pytest.mark.parametrize(("model", "fields"), _SPECS)
def test_every_editable_field_has_a_column(model, fields) -> None:
    columns = set(model.__table__.columns.keys())
    missing = sorted(f.name for f in fields if f.name not in columns)
    assert not missing, f"{model.__tablename__} has no column for: {missing}"


@pytest.mark.parametrize(("model", "fields"), _SPECS)
def test_every_editable_field_kind_matches_its_column_type(model, fields) -> None:
    mismatched = []
    for spec in fields:
        column = model.__table__.columns.get(spec.name)
        if column is None:
            continue  # reported by the test above
        expected = _EXPECTED_COLUMN_TYPE[spec.kind]
        if not isinstance(column.type, expected):
            mismatched.append(f"{spec.name}: kind {spec.kind!r} vs column {column.type}")
    assert not mismatched, f"{model.__tablename__}: {mismatched}"
