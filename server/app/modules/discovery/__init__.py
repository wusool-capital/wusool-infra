"""Finds new sellers outside the CRM (via public search) and, on request,
turns one into a real `seller_roles` row — CREATE, as opposed to
`enrichment`'s UPDATE of an existing row. This module runs no dedupe check
of its own: it hands every discovered lead straight to `SellerDraftPort`,
and `ddl_commands`' own `/add-seller` search
(`organization_selection_modal`) is the only dedupe in the pipeline — an
existing org with no active seller role still gets the prefill, an
existing org that already has one is routed to `/edit-seller` instead.

Writes are delegated through `SellerDraftPort` — this module never talks to
Attio or Postgres directly; `ddl_commands` implements the adapter and
`server/main.py` wires it (see
`ddl_commands/providers/discovery/seller_draft_adapter.py`).

Public cross-module facade — see the module-boundary rule in
`server/tests/test_architecture.py`: other modules may only import names
listed in `__all__` here.
"""

from app.modules.discovery.api.lead_flow import find_and_post_leads
from app.modules.discovery.application.ports.seller_draft import SellerDraftPort
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.leads import DiscoveredLead

__all__ = ["DiscoveredLead", "SellerDraft", "SellerDraftPort", "find_and_post_leads"]
