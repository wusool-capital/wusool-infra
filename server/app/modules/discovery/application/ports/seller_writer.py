"""What discovery needs from the CRM, without a database of its own: look a
lead up, and create it as a seller. `ddl_commands` implements it and
`server/main.py` wires it, same hand-off shape as `SellerDraftPort`.
"""

from typing import Protocol

from app.modules.discovery.domain.crm import CrmMatch
from app.modules.discovery.domain.drafts import SellerDraft
from app.modules.discovery.domain.leads import DiscoveredLead
from app.modules.discovery.domain.outcome import CreatedSeller, UnverifiedSeller


class SellerWriterPort(Protocol):
    async def find_existing(self, lead: DiscoveredLead) -> CrmMatch: ...

    async def enrich_and_create(
        self, draft: SellerDraft, *, enrichment_timeout_s: float
    ) -> CreatedSeller | UnverifiedSeller:
        """Enriches (basic tier) within `enrichment_timeout_s`, then writes
        once, Attio first. A timeout only skips enrichment. Returns
        `UnverifiedSeller` without writing when the enriched fields came from
        a provider whose website doesn't match the lead's Maps website.

        Raises `SellerWriteError` when the write fails.
        """
        ...
