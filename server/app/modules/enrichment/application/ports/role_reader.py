"""Reads the current value of every enrichable field for a target, so
`EnrichMixin.propose` can skip fields that are already populated, plus the
company context (domain, sector, HQ country, ...) a research-tier query can
use to search/verify more precisely. One method, not two: both are read off
the same role+organization row, so a single combined call is what actually
avoids a second database round trip — see `SqlAlchemyRoleReader.load`.
"""

from typing import Protocol

from app.modules.enrichment.domain.linkedin import LinkedInTargets
from app.modules.enrichment.domain.research_context import CompanyContext
from app.modules.enrichment.domain.targets import EnrichmentTarget
from app.modules.utilities.domain.json_types import JsonObject


class RoleReaderPort(Protocol):
    async def load(self, target: EnrichmentTarget) -> tuple[JsonObject, CompanyContext]: ...

    async def load_linkedin_targets(
        self, target: EnrichmentTarget, *, include_contacts: bool = True
    ) -> LinkedInTargets:
        """The company page, and the role's contacts (capped) unless
        `include_contacts` is off, for a LinkedIn scan."""
        ...
