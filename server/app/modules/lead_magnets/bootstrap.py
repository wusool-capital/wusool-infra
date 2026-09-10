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
from app.modules.lead_magnets.domain.shared.tool_run import SubjectRefs
from app.modules.lead_magnets.persistence.database import get_sessionmaker
from app.modules.lead_magnets.persistence.tool_runs_repository import ToolRunsRepository
from app.modules.lead_magnets.providers.attio.role_writer import AttioRoleWriter
from app.modules.lead_magnets.providers.bedrock.client import LeadBedrockClient
from app.modules.lead_magnets.providers.firecrawl.client import FirecrawlSearchClient
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

    def __init__(self, writer: AttioRoleWriter) -> None:
        self._writer = writer

    async def write(self, *, tool: str, payload: JsonObject, ai: JsonObject) -> SubjectRefs:
        entry_values = ai.get("entry_values")
        if not isinstance(entry_values, dict):
            entry_values = {}
        if tool == "buyer_network":
            return await self._writer.write_buyer_role(
                organization_name=payload.get("org_name") or "Unknown",
                domain=payload.get("domain"),
                org_type=[v for v in payload.get("org_type") or [] if isinstance(v, str)],
                sector_focus=[v for v in payload.get("sector_focus") or [] if isinstance(v, str)],
                entry_values=entry_values,
            )
        return await self._writer.write_seller_role(
            organization_name=payload.get("company") or payload.get("company_name") or "Unknown",
            domain=payload.get("domain"),
            entry_values=entry_values,
            # The tool's own value; the writer maps it and raises on an
            # unknown one rather than dropping it.
            sector=payload.get("peer_key") or payload.get("sector"),
        )


def build_valuation_ai() -> ValuationAi:
    return ValuationAi(build_llm(), build_search())


def build_submission_service(session: AsyncSession) -> LeadMagnetService:
    """Every tool's pipeline is reachable from the tool name alone, so the
    same service serves a fresh request and a sweeper resume."""
    return LeadMagnetService(
        tool_runs=build_tool_runs(session),
        attio=_RoleAttioWriter(build_role_writer()),
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
