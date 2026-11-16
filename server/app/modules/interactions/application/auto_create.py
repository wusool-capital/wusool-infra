"""One auto-create round: new Persons and Organizations in Attio for outside contacts."""

import logging
from dataclasses import dataclass, replace

from app.modules.interactions.application.ports.attio_writer import WritesNotAllowedError
from app.modules.interactions.application.ports.auto_create import (
    CandidateSourcePort,
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
        config: AutoCreateConfig,
    ) -> None:
        self._source = source
        self._directory = directory
        self._creator = creator
        self._config = config
        # Organizations made by this process, until the webhook brings them into Postgres.
        self._created_orgs: dict[str, str] = {}

    async def run_round(self) -> AutoCreateReport:
        config = self._config
        candidates = await self._source.candidates(config.internal_domains)
        directory = await self._directory.load()
        report = AutoCreateReport(dry_run=config.dry_run)
        planned_domains: set[str] = set()
        for candidate in candidates:
            if not is_creatable(
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
            org_id = link.organization_id or self._created_orgs.get(domain)
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
                if await self._creator.person_exists(candidate.email):
                    report = replace(report, existing=report.existing + 1)
                    continue
                if org_id is None:
                    org_id = await self._creator.create_organization(
                        organization_name(domain), domain
                    )
                    self._created_orgs[domain] = org_id
                    report = replace(report, created_orgs=report.created_orgs + 1)
                await self._creator.create_person(
                    person_name(candidate.name, candidate.email), candidate.email, org_id
                )
                report = replace(report, created_people=report.created_people + 1)
            except WritesNotAllowedError:
                raise
            except Exception:
                # One bad address must not stop the round; it is retried next round.
                logger.exception("interactions_auto_create_failed")
                report = replace(report, failed=report.failed + 1)
        return report
