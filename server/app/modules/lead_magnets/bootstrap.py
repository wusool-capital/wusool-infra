"""Composition root. The only place concrete providers and repositories are
constructed and wired into use cases.

Background work opens and owns its own session: a request-scoped session is
committed and closed the moment the FastAPI dependency resumes, so handing
one to `BackgroundTasks` would use it after close.
"""

import asyncio
import dataclasses
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attio import attio_is_test, get_attio_client
from app.modules.lead_magnets.application.shared.service import LeadMagnetService
from app.modules.lead_magnets.application.shared.sweeper import sweep_once
from app.modules.lead_magnets.application.valuation.valuation_ai import ValuationAi
from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.domain.shared.attio_values import DealType, lead_source_detail_label
from app.modules.lead_magnets.domain.shared.dedup import (
    domain_matches,
    normalise_domain,
    normalise_name,
)
from app.modules.lead_magnets.domain.shared.schemas import (
    AttioIdentityPayload,
    BuyerNetworkPayload,
)
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.lead_magnets.persistence.database import get_sessionmaker
from app.modules.lead_magnets.persistence.tool_runs_repository import ToolRunsRepository
from app.modules.lead_magnets.providers.attio.deal_writer import AttioDealWriter
from app.modules.lead_magnets.providers.attio.person_writer import AttioPersonWriter
from app.modules.lead_magnets.providers.attio.role_writer import AttioRoleWriter
from app.modules.lead_magnets.providers.bedrock.client import LeadBedrockClient
from app.modules.lead_magnets.providers.firecrawl.client import FirecrawlSearchClient
from app.modules.notifications import EmailSenderPort, SesMailer, get_ses_client
from app.modules.organizations import OrganizationRepository
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


def build_llm() -> LeadBedrockClient:
    return LeadBedrockClient()


def build_search() -> FirecrawlSearchClient:
    return FirecrawlSearchClient(get_settings().firecrawl_api_key)


def build_role_writer() -> AttioRoleWriter:
    return AttioRoleWriter(get_attio_client(), is_test=attio_is_test())


def build_person_writer() -> AttioPersonWriter:
    return AttioPersonWriter(get_attio_client(), is_test=attio_is_test())


def build_deal_writer() -> AttioDealWriter:
    settings = get_settings()
    return AttioDealWriter(
        get_attio_client(),
        is_test=attio_is_test(),
        owner_id=settings.lead_magnet_deal_owner_id,
        fallback_owner_id=settings.lead_magnet_deal_owner_fallback_id,
    )


def build_tool_runs(session: AsyncSession) -> ToolRunsRepository:
    return ToolRunsRepository(session)


def build_lead_magnet_mailer() -> EmailSenderPort:
    settings = get_settings()
    client = get_ses_client(region_name=settings.aws_region)
    return SesMailer(client)


class _RoleAttioWriter:
    """Adapts `AttioRoleWriter` (+ `AttioPersonWriter`) to `AttioWriterPort`.

    The port is tool-agnostic — `submit.py` knows nothing about seller or
    buyer roles, or people — so the per-tool value mapping, and which Attio
    list/object a tool writes to, is resolved here, at the composition
    root, rather than leaking into the use case.
    """

    def __init__(
        self,
        writer: AttioRoleWriter,
        organizations: OrganizationRepository,
        person: AttioPersonWriter,
        deal: AttioDealWriter,
    ) -> None:
        self._writer = writer
        self._organizations = organizations
        self._person = person
        self._deal = deal

    async def _find_existing_org(self, *, name: str, domain: str | None) -> str | None:
        """Postgres-side dedup, per `domain/shared/dedup.py`'s own docstring:
        without this, every submission from a company Attio has already seen
        creates a second Attio organisation instead of reusing the first.

        Name-similarity search first (candidates), `domain_matches` to
        confirm identity — domain alone is never enough (a holdco domain can
        legitimately cover several distinct businesses), and an empty
        `domain` always returns `None` rather than matching by name alone.
        `write_seller_role`/`write_buyer_role` still call
        `assert_organization_in_scope` on whatever this returns, so a match
        against the wrong `is_test` half of the shared workspace fails the
        write cleanly rather than corrupting it — Postgres has no `is_test`
        column to pre-filter on.
        """
        if not normalise_domain(domain):
            return None
        for candidate in await self._organizations.search_by_name(normalise_name(name)):
            if domain_matches(candidate.domains, domain):
                return candidate.attio_id
        return None

    async def write(self, *, tool: str, payload: JsonObject, ai: JsonObject) -> SubjectRefs:
        entry_values = ai.get("entry_values")
        if not isinstance(entry_values, dict):
            entry_values = {}
        lead_source_detail = lead_source_detail_label(tool)

        if tool == "buyer_network":
            buyer = BuyerNetworkPayload.model_validate(payload)
            name = buyer.org_name or "Unknown"
            subjects = await self._writer.write_buyer_role(
                organization_name=name,
                domain=buyer.domain,
                org_type=buyer.org_type,
                target_verticals=buyer.sector_focus,
                entry_values=entry_values,
                organization_attio_id=await self._find_existing_org(name=name, domain=buyer.domain),
                lead_source_detail=lead_source_detail,
            )
            subjects = await self._with_person(
                subjects,
                name=buyer.full_name,
                email=buyer.email,
                linkedin=buyer.linkedin_url,
            )
            return await self._with_deal(subjects, deal_type="Buy-side")

        seller = AttioIdentityPayload.model_validate(payload)
        # `company_name` is not a field any real request ever sends — kept as
        # a raw fallback rather than promoted onto `AttioIdentityPayload`,
        # matching the pre-existing behaviour exactly.
        name = seller.company or payload.get("company_name") or "Unknown"
        subjects = await self._writer.write_seller_role(
            organization_name=name,
            domain=seller.domain,
            entry_values=entry_values,
            # `sector` wins when present: benchmark tech-mode sends it
            # because its own `peer_key` is a funding stage there, not a
            # sector (`api/schemas.py::BenchmarkRequest.sector`'s own
            # docstring). Every other case — SME-mode benchmark (no
            # separate `sector` sent; `peer_key` already is the CRM
            # sector), valuation, readiness (no `peer_key` at all) —
            # resolves exactly as before, since only one of the two is
            # ever actually present for them.
            sector=seller.sector or seller.peer_key,
            description=seller.description,
            # `geography` wins when present (benchmark/valuation); `country`
            # is readiness's own name for the same org attribute — never
            # both at once today, kept symmetric with the `sector`/`peer_key`
            # precedence above rather than routing by tool name.
            hq_country=seller.geography or seller.country,
            funding_raised=seller.capital_raised,
            organization_attio_id=await self._find_existing_org(name=name, domain=seller.domain),
            lead_source_detail=lead_source_detail,
        )
        subjects = await self._with_person(
            subjects, name=seller.name, email=seller.email, phone=seller.phone
        )
        return await self._with_deal(subjects, deal_type="Sell-side")

    async def _with_person(
        self,
        subjects: SubjectRefs,
        *,
        name: str | None,
        email: str | None,
        linkedin: str | None = None,
        phone: str | None = None,
    ) -> SubjectRefs:
        """Best-effort: a person-write failure must never lose the lead the
        org/role write above already landed, and must never make the
        sweeper re-enter this whole method — see `person_writer.py`'s
        module docstring and this module's README for why.
        """
        try:
            person = await self._person.write(
                name=name,
                email=email,
                organization_attio_id=subjects.org_attio_id,
                linkedin=linkedin,
                phone=phone,
            )
        except Exception as exc:  # noqa: BLE001 - the org/role write already succeeded
            logger.warning("lead_magnet_person_write_failed error=%s", exc)
            return subjects
        if person is None:
            return subjects
        person_attio_id, person_name = person
        return dataclasses.replace(
            subjects, person_attio_id=person_attio_id, person_name=person_name
        )

    async def _with_deal(self, subjects: SubjectRefs, *, deal_type: DealType) -> SubjectRefs:
        """Best-effort, same rule as `_with_person`: the org/role write above
        has already landed the lead, and a deal failure must not make the
        sweeper re-enter this whole method.
        """
        try:
            deal = await self._deal.write(
                org_attio_id=subjects.org_attio_id,
                org_name=subjects.org_name or "Unknown",
                deal_type=deal_type,
            )
        except Exception as exc:  # noqa: BLE001 - the org/role write already succeeded
            logger.warning("lead_magnet_deal_write_failed error=%s", exc)
            return subjects
        if deal is None:
            return subjects
        deal_attio_id, deal_web_url = deal
        return dataclasses.replace(subjects, deal_attio_id=deal_attio_id, deal_web_url=deal_web_url)


def build_valuation_ai() -> ValuationAi:
    return ValuationAi(build_llm(), build_search())


def build_submission_service(session: AsyncSession) -> LeadMagnetService:
    """Every tool's pipeline is reachable from the tool name alone, so the
    same service serves a fresh request and a sweeper resume."""
    settings = get_settings()
    return LeadMagnetService(
        tool_runs=build_tool_runs(session),
        attio=_RoleAttioWriter(
            build_role_writer(),
            OrganizationRepository(session),
            build_person_writer(),
            build_deal_writer(),
        ),
        llm=build_llm(),
        mailer=build_lead_magnet_mailer(),
        email_from=settings.lead_magnet_email_from,
        email_to=settings.lead_magnet_email_to.split(),
    )


async def run_completion(run_id: UUID) -> None:
    """`BackgroundTasks` entrypoint for steps 3-5 of the write contract.

    Opens its own session and commits it. Never raises: the lead is already
    recorded, so a failure here is the sweeper's problem.
    """
    async with get_sessionmaker()() as session:
        try:
            repository = build_tool_runs(session)
            run = await repository.get(run_id)
            if run is None:
                logger.warning("lead_magnet_completion_missing_run run_id=%s", run_id)
                return
            service = build_submission_service(session)
            await service.complete(run)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.exception("lead_magnet_completion_failed run_id=%s", run_id)


async def run_sweeper_forever() -> None:
    """Started once by `main.py`'s lifespan, cancelled on shutdown.

    Drains whatever the write contract left unfinished — see
    `application/shared/sweeper.py`. A pass runs immediately on every start
    (so a container restart doesn't wait out a full interval before
    draining a backlog), then again every `lead_magnet_sweeper_interval_s`.
    A failed pass is logged, never stops the loop: a stuck sweep matters far
    less than the loop dying silently and nothing ever retrying again.
    """
    settings = get_settings()
    while True:
        try:
            async with get_sessionmaker()() as session:
                tool_runs = build_tool_runs(session)
                service = build_submission_service(session)
                resumed = await sweep_once(
                    tool_runs, service, stale_after_s=settings.lead_magnet_sweeper_stale_after_s
                )
                await session.commit()
            if resumed:
                logger.info("lead_magnet_sweeper_pass resumed=%d", resumed)
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("lead_magnet_sweeper_pass_failed")
        await asyncio.sleep(settings.lead_magnet_sweeper_interval_s)
