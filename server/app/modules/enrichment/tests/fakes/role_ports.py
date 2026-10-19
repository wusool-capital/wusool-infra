"""Fake `RoleReaderPort`/`EnrichmentReviewPort` for tests — in-memory, no DB/Slack."""

from typing import Any

from app.modules.enrichment.application.ports.review import EnrichmentReviewPort
from app.modules.enrichment.application.ports.role_reader import RoleReaderPort
from app.modules.enrichment.domain.linkedin import LinkedInTargets
from app.modules.enrichment.domain.proposals import ProposedFieldValue
from app.modules.enrichment.domain.research_context import CompanyContext
from app.modules.enrichment.domain.targets import EnrichmentTarget


class FakeRoleReader(RoleReaderPort):
    def __init__(
        self,
        values: dict[str, Any] | None = None,
        context: CompanyContext | None = None,
        linkedin_targets: LinkedInTargets | None = None,
    ) -> None:
        self.values = values or {}
        self._context = context
        self._linkedin_targets = linkedin_targets or LinkedInTargets()
        self.include_contacts_calls: list[bool] = []

    async def load(self, target: EnrichmentTarget) -> tuple[dict[str, Any], CompanyContext]:
        return dict(self.values), self._context or CompanyContext(org_name=target.org_name)

    async def load_linkedin_targets(
        self, target: EnrichmentTarget, *, include_contacts: bool = True
    ) -> LinkedInTargets:
        self.include_contacts_calls.append(include_contacts)
        if include_contacts:
            return self._linkedin_targets
        return LinkedInTargets(company_url=self._linkedin_targets.company_url)


class FakeReviewPort(EnrichmentReviewPort):
    def __init__(self) -> None:
        self.calls: list[tuple[EnrichmentTarget, tuple[ProposedFieldValue, ...]]] = []

    async def open_review_form(
        self,
        *,
        trigger_id: str,
        target: EnrichmentTarget,
        values: tuple[ProposedFieldValue, ...],
        channel_id: str,
        requested_by: str,
        card_token: str | None = None,
    ) -> None:
        self.calls.append((target, values))
