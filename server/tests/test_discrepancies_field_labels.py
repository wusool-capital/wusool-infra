"""`discrepancies.domain.vocabulary.CRITERION_FIELD_LABELS` copies
`ddl_commands.api.buyers.BUYER_ROLE_FIELDS` labels by hand, since a `domain/`
layer must not reach into `ddl_commands`' `api/` layer. A renamed field would
otherwise send advisors looking for a field `/edit-buyer` no longer shows.
"""

from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME
from app.modules.discrepancies.domain.vocabulary import CRITERION_FIELD_LABELS


def test_field_labels_match_the_buyer_role_field_spec() -> None:
    live_labels = {field.label for field in BUYER_ROLE_FIELDS_BY_NAME.values()}
    copied = {label for labels in CRITERION_FIELD_LABELS.values() for label in labels}
    assert copied <= live_labels
