"""What enrichment proposes for one target, before an operator confirms
anything. No value here is ever written on its own — see `RoleUpdaterPort`.
"""

from dataclasses import dataclass
from typing import Any

from app.modules.enrichment.domain.field_plans import WriteTarget
from app.modules.enrichment.domain.targets import EnrichmentTarget


@dataclass(frozen=True)
class ProposedFieldValue:
    field_name: str
    write_target: WriteTarget
    current: Any | None
    proposed: Any
    source_url: str
    confidence: float
    rationale: str


@dataclass(frozen=True)
class EnrichmentProposal:
    target: EnrichmentTarget
    values: tuple[ProposedFieldValue, ...]
    generated_by_model: str
