"""`ddl_commands`' criterion -> form-field table copies `discrepancies`'
`Criterion` values and the buyer field names by hand (module boundaries). Keeps
a rename from silently opening an empty or wrong "Edit buyer" form.
"""

from app.modules.ddl_commands.api.buyers import BUYER_FORM_FIELDS
from app.modules.ddl_commands.api.slack.handlers.actions import _CRITERION_BUYER_FIELDS
from app.modules.discrepancies.domain.vocabulary import Criterion


def test_every_editable_criterion_maps_to_real_form_fields() -> None:
    assert set(_CRITERION_BUYER_FIELDS) <= {c.value for c in Criterion}
    editable = {f.name for f in BUYER_FORM_FIELDS}
    assert all(set(names) <= editable for names in _CRITERION_BUYER_FIELDS.values())
