"""The seam `LinkedInMixin` uses to remember what a LinkedIn scan found, so a
re-run reports only what is new. Implemented by `persistence/linkedin_history.py`.
"""

from typing import Protocol

from app.modules.enrichment.domain.linkedin import LinkedInScan
from app.modules.enrichment.domain.targets import EnrichmentTarget


class LinkedInHistoryPort(Protocol):
    async def record(self, target: EnrichmentTarget, scan: LinkedInScan) -> LinkedInScan:
        """Stores the scan and returns only its new posts and job changes.
        `contacts_without_linkedin` and `contacts_scanned` pass through. Raises
        on a storage failure: the caller decides whether to fall back."""
        ...
