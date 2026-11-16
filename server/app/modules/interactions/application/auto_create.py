"""One auto-create round: new Persons and Organizations in Attio for outside contacts."""

import logging
from collections import Counter
from dataclasses import dataclass, replace

from app.modules.interactions.application.ports.attio_writer import WritesNotAllowedError
from app.modules.interactions.application.ports.auto_create import (
    CandidateSourcePort,
    CreatedKeysPort,
    CreatedKind,
    RecordCreatorPort,
)
from app.modules.interactions.application.ports.record_directory import RecordDirectoryPort
from app.modules.interactions.domain.auto_create import (
    organization_name,
    person_name,
    registrable_domain,
)
from app.modules.interactions.domain.creatable import is_creatable
from app.modules.interactions.domain.linking import resolve_link

logger = logging.getLogger(__name__)

# An address Attio keeps rejecting is dropped until the next restart, so it can't use up
# every round's cap while later candidates wait.
_MAX_FAILURES = 3


@dataclass(frozen=True)
class AutoCreateConfig:
    internal_domains: tuple[str, ...]
    free_email_domains: frozenset[str]
    max_per_round: int
    dry_run: bool


@dataclass(frozen=True)
class AutoCreateReport:
    created_people: int = 0
    created_orgs: int = 0
    # Already in Attio or Postgres: the next pass links them, nothing is created.
    existing: int = 0
    skipped: int = 0
    # A shared address or domain: left for a person to review.
    shared: int = 0
    failed: int = 0
    hit_cap: bool = False
    dry_run: bool = False


class AutoCreateService:
    def __init__(
        self,
        source: CandidateSourcePort,
        directory: RecordDirectoryPort,
        creator: RecordCreatorPort,
        keys: CreatedKeysPort,
        config: AutoCreateConfig,
    ) -> None:
        self._source = source
        self._directory = directory
        self._creator = creator
        self._keys = keys
        self._config = config
        self._failures: Counter[str] = Counter()

    async def run_round(self) -> AutoCreateReport:
        config = self._config
        candidates = await self._source.candidates(config.internal_domains)
        directory = await self._directory.load()
        report = AutoCreateReport(dry_run=config.dry_run)
        planned_domains: set[str] = set()
        for candidate in candidates:
            if self._failures[candidate.email] >= _MAX_FAILURES or not is_creatable(
                candidate.email,
                free_email_domains=config.free_email_domains,
                # Bulk mail is dropped at ingest, so none reaches this point.
                has_list_unsubscribe=False,
                two_way_thread=candidate.two_way_thread,
                attended_meeting=candidate.attended_meeting,
                internal_domains=config.internal_domains,
            ):
                report = replace(report, skipped=report.skipped + 1)
                continue
            link = resolve_link(candidate.email, directory)
            if link.ambiguity is not None:
                report = replace(report, shared=report.shared + 1)
                continue
            if link.person_id is not None:
                report = replace(report, existing=report.existing + 1)
                continue
            attempts = report.created_people + report.failed
            if not config.dry_run and attempts >= config.max_per_round:
                report = replace(report, hit_cap=True)
                break
            domain = registrable_domain(candidate.domain)
            org_id = link.organization_id or await self._keys.get(CreatedKind.ORGANIZATION, domain)
            if config.dry_run:
                new_org = org_id is None and domain not in planned_domains
                planned_domains.add(domain)
                report = replace(
                    report,
                    created_people=report.created_people + 1,
                    created_orgs=report.created_orgs + int(new_org),
                )
                continue
            try:
                report = await self._create(candidate.email, candidate.name, domain, org_id, report)
            except WritesNotAllowedError:
                raise
            except Exception:
                # One bad address must not stop the round; it is retried, up to a limit.
                logger.exception("interactions_auto_create_failed")
                self._failures[candidate.email] += 1
                report = replace(report, failed=report.failed + 1)
        return report

    async def _create(
        self,
        email: str,
        name: str | None,
        domain: str,
        org_id: str | None,
        report: AutoCreateReport,
    ) -> AutoCreateReport:
        # Our own record of what we made comes first: it survives a restart and a late webhook.
        if await self._keys.get(CreatedKind.PERSON, email) or await self._creator.person_exists(
            email
        ):
            return replace(report, existing=report.existing + 1)
        if org_id is None:
            org_id = await self._creator.create_organization(organization_name(domain), domain)
            await self._keys.save(CreatedKind.ORGANIZATION, domain, org_id)
            report = replace(report, created_orgs=report.created_orgs + 1)
        person_id = await self._creator.create_person(person_name(name, email), email, org_id)
        await self._keys.save(CreatedKind.PERSON, email, person_id)
        self._failures.pop(email, None)
        return replace(report, created_people=report.created_people + 1)
