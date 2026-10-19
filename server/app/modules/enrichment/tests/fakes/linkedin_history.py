"""Fake `LinkedInHistoryPort` for tests — remembers ids in memory."""

from app.modules.enrichment.application.ports.linkedin_history import LinkedInHistoryPort
from app.modules.enrichment.domain.linkedin import LinkedInScan, job_change_key
from app.modules.enrichment.domain.targets import EnrichmentTarget


class FakeLinkedInHistory(LinkedInHistoryPort):
    def __init__(self, *, error: Exception | None = None) -> None:
        self._seen: set[str] = set()
        self._error = error
        self.calls = 0

    async def record(self, target: EnrichmentTarget, scan: LinkedInScan) -> LinkedInScan:
        self.calls += 1
        if self._error:
            raise self._error
        posts = tuple(p for p in scan.posts if p.external_id not in self._seen)
        changes = tuple(c for c in scan.job_changes if job_change_key(c) not in self._seen)
        self._seen |= {p.external_id for p in posts} | {job_change_key(c) for c in changes}
        return LinkedInScan(
            job_changes=changes,
            posts=posts,
            contacts_without_linkedin=scan.contacts_without_linkedin,
            contacts_scanned=scan.contacts_scanned,
        )
