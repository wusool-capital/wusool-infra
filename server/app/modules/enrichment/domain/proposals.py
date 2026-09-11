"""What enrichment proposes for one target, before an operator confirms
anything. No value here is ever written on its own — see `RoleUpdaterPort`.
"""

from dataclasses import dataclass
from datetime import date

from app.modules.enrichment.domain.field_plans import WriteTarget
from app.modules.enrichment.domain.targets import EnrichmentTarget
from app.modules.utilities.domain.json_types import JsonObject

# Every shape a field's value can actually take across this module's
# `FieldKind`s: `str` (text/multiline/select/employee_range/linkedin/...),
# `float` (currency/number/percent once coerced), `bool`, `date`, `list[str]`
# (multi_select_text), and the currency field's own raw DB-storage shape
# (`{"amount": ..., "currency": "USD"}`) for `current` specifically.
FieldValue = str | float | bool | int | date | list[str] | JsonObject


@dataclass(frozen=True)
class ProposedFieldValue:
    field_name: str
    write_target: WriteTarget
    current: FieldValue | None
    proposed: FieldValue
    source_url: str
    confidence: float
    rationale: str


@dataclass(frozen=True)
class EnrichmentProposal:
    target: EnrichmentTarget
    values: tuple[ProposedFieldValue, ...]
    generated_by_model: str
