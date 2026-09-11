"""Buyer/seller field enrichment: research an existing role's missing
fields from public sources, propose values, and hand the proposal off for
review. Writes are delegated through `EnrichmentReviewPort` — this module
never talks to Attio or Postgres directly; `ddl_commands` implements the
adapter (opening its own real `/edit-seller`/`/edit-buyer` modal, prefilled)
and `server/main.py` wires it (see that module's
`providers/enrichment/review_adapter.py`).

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.enrichment.api.enrich_flow import enrich_and_post
from app.modules.enrichment.application.ports.review import EnrichmentReviewPort
from app.modules.enrichment.application.ports.role_reader import RoleReaderPort
from app.modules.enrichment.domain.field_plans import WriteTarget
from app.modules.enrichment.domain.proposals import EnrichmentProposal, ProposedFieldValue
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind

__all__ = [
    "EnrichmentProposal",
    "EnrichmentReviewPort",
    "EnrichmentTarget",
    "EnrichmentTargetKind",
    "ProposedFieldValue",
    "RoleReaderPort",
    "WriteTarget",
    "enrich_and_post",
]
