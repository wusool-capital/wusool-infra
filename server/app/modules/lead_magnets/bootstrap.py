"""Composition root. The only place concrete providers and repositories are
constructed and wired into use cases.

Background work opens and owns its own session: a request-scoped session is
committed and closed the moment the FastAPI dependency resumes, so handing
one to `BackgroundTasks` would use it after close.
"""

import asyncio
import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attio import attio_is_test, get_attio_client
from app.modules.lead_magnets.application.shared.service import LeadMagnetService
from app.modules.lead_magnets.application.shared.sweeper import sweep_once
from app.modules.lead_magnets.application.valuation.valuation_ai import ValuationAi
from app.modules.lead_magnets.config import get_settings
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
from app.modules.lead_magnets.providers.attio.role_writer import AttioRoleWriter
from app.modules.lead_magnets.providers.bedrock.client import LeadBedrockClient
from app.modules.lead_magnets.providers.firecrawl.client import FirecrawlSearchClient
from app.modules.organizations import OrganizationRepository
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


def build_llm() -> LeadBedrockClient:
    return LeadBedrockClient()


def build_search() -> FirecrawlSearchClient:
    return FirecrawlSearchClient(get_settings().firecrawl_api_key)


def build_role_writer() -> AttioRoleWriter:
    return AttioRoleWriter(get_attio_client(), is_test=attio_is_test())


def build_tool_runs(session: AsyncSession) -> ToolRunsRepository:
    return ToolRunsRepository(session)


class _RoleAttioWriter:
    """Adapts `AttioRoleWriter` to `AttioWriterPort`.

    The port is tool-agnostic — `submit.py` knows nothing about seller or
    buyer roles — so the per-tool value mapping, and which Attio list a tool
    writes to, is resolved here, at the composition root, rather than
    leaking into the use case.
    """

    def __init__(self, writer: AttioRoleWriter, organizations: OrganizationRepository) -> None:
        self._writer = writer
        self._organizations = organizations

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

        if tool == "buyer_network":
            buyer = BuyerNetworkPayload.model_validate(payload)
            name = buyer.org_name or "Unknown"
            return await self._writer.write_buyer_role(
                organization_name=name,
                domain=buyer.domain,
                org_type=buyer.org_type,
                sector_focus=buyer.sector_focus,
                entry_values=entry_values,
                organization_attio_id=await self._find_existing_org(name=name, domain=buyer.domain),
            )

        seller = AttioIdentityPayload.model_validate(payload)
        # `company_name` is not a field any real request ever sends — kept as
        # a raw fallback rather than promoted onto `AttioIdentityPayload`,
        # matching the pre-existing behaviour exactly.
        name = seller.company or payload.get("company_name") or "Unknown"
        return await self._writer.write_seller_role(
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
            organization_attio_id=await self._find_existing_org(name=name, domain=seller.domain),
        )


def build_valuation_ai() -> ValuationAi:
    return ValuationAi(build_llm(), build_search())


def build_submission_service(session: AsyncSession) -> LeadMagnetService:
    """Every tool's pipeline is reachable from the tool name alone, so the
    same service serves a fresh request and a sweeper resume."""
    return LeadMagnetService(
        tool_runs=build_tool_runs(session),
        attio=_RoleAttioWriter(build_role_writer(), OrganizationRepository(session)),
        llm=build_llm(),
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
