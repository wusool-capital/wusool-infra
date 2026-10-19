"""Fake `LinkedInHistoryPort` for tests — remembers ids in memory."""

from dataclasses import replace

from app.modules.enrichment.application.ports.linkedin_history import LinkedInHistoryPort
from app.modules.enrichment.domain.linkedin import LinkedInScan, job_change_key
from app.modules.enrichment.domain.targets import EnrichmentTarget


class FakeLinkedInHistory(LinkedInHistoryPort):
    def __init__(self, *, error: Exception | None = None) -> None:
        self._seen: set[str] = set()
        self._error = error
        self.calls = 0
        self.requested_by: list[str | None] = []
        self.failures: list[str | None] = []

    async def record(
        self,
        target: EnrichmentTarget,
        scan: LinkedInScan,
        *,
        requested_by: str | None = None,
        failure: str | None = None,
    ) -> LinkedInScan:
        self.calls += 1
        self.requested_by.append(requested_by)
        self.failures.append(failure)
        if self._error:
            raise self._error
        posts = tuple(p for p in scan.posts if p.external_id not in self._seen)
        changes = tuple(c for c in scan.job_changes if job_change_key(c) not in self._seen)
        self._seen |= {p.external_id for p in posts} | {job_change_key(c) for c in changes}
        return replace(scan, job_changes=changes, posts=posts)
