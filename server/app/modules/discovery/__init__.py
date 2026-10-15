"""Finds new sellers outside the CRM (via public search), checks each against
the CRM, and auto-creates the ones that are genuinely new as `seller_roles`
rows — CREATE, as opposed to `enrichment`'s UPDATE of an existing row.

The pre-filter replaces the human `/add-seller` step as the dedupe gate: an
exact `place_id` or domain match skips a lead; a name-only match is *not*
created either, and is only counted in the outcome (`possible_duplicates`); it
doesn't use up one of the run's slots. A person can still add it with
`/add-seller`, whose org search is the final check.

CRM reads and writes are delegated through `SellerWriterPort`/`SellerDraftPort`
— this module never touches Attio or the CRM tables; it owns only
`discovery_reviews` (leads awaiting a website review). `ddl_commands`
implements the adapters and `server/main.py` wires them (see
`ddl_commands/providers/discovery/`).

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.discovery.api.lead_flow import discover_and_create_sellers, mark_review_posted
from app.modules.discovery.api.slack.review_card import mark_review_card_added, store_review_card
from app.modules.discovery.api.slack.views import (
    build_needs_review_blocks,
)
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.application.ports.seller_writer import SellerWriterPort
from app.modules.discovery.domain.crm import CrmMatch, CrmMatchKind
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import (
    CreatedSeller,
    DiscoveryOutcome,
    FailedLead,
    ReviewValue,
    SellerWriteError,
    UnverifiedSeller,
)

__all__ = [
    "CreatedSeller",
    "CrmMatch",
    "CrmMatchKind",
    "DiscoveredLead",
    "DiscoveryOutcome",
    "FailedLead",
    "ReviewValue",
    "SellerDraft",
    "SellerDraftPort",
    "SellerWriteError",
    "SellerWriterPort",
    "UnverifiedSeller",
    "build_needs_review_blocks",
    "discover_and_create_sellers",
    "mark_review_card_added",
    "mark_review_posted",
    "store_review_card",
]
