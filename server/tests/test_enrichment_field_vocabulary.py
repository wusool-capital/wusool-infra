"""`enrichment.domain.field_plans.EnrichableField` and `ddl_commands`' own
`FieldSpec` maps hold two separate copies of the same field vocabulary —
`enrichment` must never import `ddl_commands` (see
`enrichment/__init__.py`'s docstring), so it redeclares the `kind` and, for a
`select`/`multi_select_text` field, the fixed `options` a proposed value must
match. A field added or reworded on the `ddl_commands` side but not mirrored
here silently breaks the enrichment flow: the LLM extraction prompt
(`enrich._field_line`) advertises the wrong (or no) vocabulary, and
`normalize_prefill` then drops any proposed value that doesn't match — the
field simply vanishes between the Slack proposal message and the edit form,
with no error anywhere.

Read as two Python modules rather than one file — unlike
`test_hq_country_vocabulary.py`'s JS source, both sides here are already
Python, and a top-level test importing both is unconstrained by the
architecture fitness tests, which only walk `app/modules/**`
(`test_architecture.py`'s `MODULES_ROOT`).
"""

import pytest

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.ddl_commands.api.organizations import ORGANIZATION_FIELDS_BY_NAME
from app.modules.ddl_commands.api.sellers import SELLER_ROLE_FIELDS_BY_NAME
from app.modules.enrichment.domain.field_plans import (
    BUYER_ENRICHABLE_FIELDS,
    SELLER_ENRICHABLE_FIELDS,
    EnrichableField,
    WriteTarget,
)

_FIELDS_BY_NAME_FOR_TARGET = {
    WriteTarget.ORGANIZATION: ORGANIZATION_FIELDS_BY_NAME,
    WriteTarget.SELLER_ROLE: SELLER_ROLE_FIELDS_BY_NAME,
    WriteTarget.BUYER_ROLE: BUYER_ROLE_FIELDS_BY_NAME,
}

# `hq_country` and `region` are both `multi_select_as_text` — a picker with a
# curated option subset that intentionally degrades to free text for anything
# outside it (see `dynamic_fields.render_field_block`; `hq_country`'s list is
# further governed by `test_hq_country_vocabulary.py`). `enrichment`
# deliberately carries no `options` for either, so nothing constrains its
# proposed value against `ddl_commands`' picker subset.
_EXEMPT_FROM_OPTIONS_CHECK = frozenset({"hq_country", "region"})

# Deduped by name: `ORGANIZATION_ENRICHABLE_FIELDS` is folded into both
# `SELLER_ENRICHABLE_FIELDS` and `BUYER_ENRICHABLE_FIELDS` (see
# `field_plans`'s module docstring), so the same `EnrichableField` object
# would otherwise be checked twice under the same parametrize id.
_ALL_ENRICHABLE_FIELDS = tuple(
    {f.name: f for f in SELLER_ENRICHABLE_FIELDS + BUYER_ENRICHABLE_FIELDS}.values()
)


@pytest.mark.parametrize("field", _ALL_ENRICHABLE_FIELDS, ids=lambda f: f.name)
def test_enrichable_field_matches_its_ddl_commands_field_spec(field: EnrichableField) -> None:
    fields_by_name = _FIELDS_BY_NAME_FOR_TARGET[field.write_target]
    spec = fields_by_name.get(field.name)
    assert spec is not None, (
        f"enrichment proposes {field.name!r} for {field.write_target.value}, but "
        "ddl_commands has no FieldSpec for it there"
    )
    assert spec.kind == field.kind, (
        f"{field.name!r} kind mismatch: enrichment says {field.kind!r}, "
        f"ddl_commands says {spec.kind!r}"
    )
    if field.name in _EXEMPT_FROM_OPTIONS_CHECK:
        return
    assert spec.options == field.options, (
        f"{field.name!r} options mismatch: enrichment says {field.options!r}, "
        f"ddl_commands says {spec.options!r} — the LLM prompt and the Slack "
        "prefill filter must agree, in the same order, or a valid proposal "
        "silently vanishes from the review form"
    )
