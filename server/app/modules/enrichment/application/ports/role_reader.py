"""Reads the current value of every enrichable field for a target, so
`EnrichMixin.propose` can skip fields that are already populated. Returns
plain values keyed by field name — never an ORM row.
"""

from typing import Protocol

from app.modules.enrichment.domain.research_context import CompanyContext
from app.modules.enrichment.domain.targets import EnrichmentTarget
from app.modules.utilities.domain.json_types import JsonObject


class RoleReaderPort(Protocol):
    async def current_values(self, target: EnrichmentTarget) -> JsonObject: ...

    async def company_context(self, target: EnrichmentTarget) -> CompanyContext: ...
