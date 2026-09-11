"""Keeps `enrichment`'s field plans in sync with this module's own
`FieldSpec` tables — a mismatch here means enrichment would either propose
a field this module can't write, or use a different `kind` than the field
actually has (silently wrong Attio serialization).
"""

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.enrichment.domain.field_plans import (
    BUYER_ENRICHABLE_FIELDS,
    SELLER_ENRICHABLE_FIELDS,
    WriteTarget,
)

_ROLE_FIELDS_BY_NAME = {
    WriteTarget.SELLER_ROLE: SELLER_ROLE_FIELDS_BY_NAME,
    WriteTarget.BUYER_ROLE: BUYER_ROLE_FIELDS_BY_NAME,
    WriteTarget.ORGANIZATION: ORGANIZATION_FIELDS_BY_NAME,
}


def _assert_fields_match(enrichable_fields: tuple) -> None:
    for field in enrichable_fields:
        specs = _ROLE_FIELDS_BY_NAME[field.write_target]
        assert field.name in specs, (
            f"{field.name!r} has no matching {field.write_target.value} FieldSpec in ddl_commands"
        )
        assert specs[field.name].kind == field.kind, (
            f"{field.name!r} kind mismatch: enrichment={field.kind!r} "
            f"ddl_commands={specs[field.name].kind!r}"
        )


def test_seller_enrichable_fields_match_field_specs() -> None:
    _assert_fields_match(SELLER_ENRICHABLE_FIELDS)


def test_buyer_enrichable_fields_match_field_specs() -> None:
    _assert_fields_match(BUYER_ENRICHABLE_FIELDS)
