"""Buyer/seller field enrichment: research an existing role's missing
fields from public sources, propose values, and hand the proposal off for
review. CRM writes are delegated through `EnrichmentReviewPort` — this module
never writes Attio, and its only Postgres writes are the LinkedIn scan history
(its own `linkedin_scans`, `signals`, `activities`); `ddl_commands` implements the
adapter (opening its own real `/edit-seller`/`/edit-buyer` modal, prefilled)
and `server/main.py` wires it (see that module's
`providers/enrichment/review_adapter.py`).

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.enrichment.api.enrich_flow import (
    enrich_and_post,
    propose_basic_seller_fields,
    scan_linkedin_for_role,
)
from app.modules.enrichment.application.ports.review import EnrichmentReviewPort
from app.modules.enrichment.application.ports.role_reader import RoleReaderPort
from app.modules.enrichment.domain.field_plans import WriteTarget
from app.modules.enrichment.domain.linkedin import (
    Contact,
    JobChange,
    LinkedInPost,
    LinkedInProfile,
    LinkedInScan,
)
from app.modules.enrichment.domain.proposals import (
    BasicEnrichment,
    EnrichmentProposal,
    ProposedFieldValue,
    ProviderEvidence,
)
from app.modules.enrichment.domain.targets import EnrichmentTarget, EnrichmentTargetKind

__all__ = [
    "BasicEnrichment",
    "Contact",
    "EnrichmentProposal",
    "EnrichmentReviewPort",
    "EnrichmentTarget",
    "EnrichmentTargetKind",
    "JobChange",
    "LinkedInPost",
    "LinkedInProfile",
    "LinkedInScan",
    "ProposedFieldValue",
    "ProviderEvidence",
    "RoleReaderPort",
    "WriteTarget",
    "enrich_and_post",
    "propose_basic_seller_fields",
    "scan_linkedin_for_role",
]
