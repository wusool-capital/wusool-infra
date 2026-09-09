"""Composition root. The only place concrete providers and repositories are
constructed and wired into use cases.

Background work opens and owns its own session: a request-scoped session is
committed and closed the moment the FastAPI dependency resumes, so handing
one to `BackgroundTasks` would use it after close.
"""

import logging
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.attio import attio_is_test, get_attio_client
from app.modules.lead_magnets.application.pipelines import Pipelines
from app.modules.lead_magnets.application.submit import SubmissionService
from app.modules.lead_magnets.application.valuation_ai import ValuationAi
from app.modules.lead_magnets.config import get_settings
from app.modules.lead_magnets.domain.tool_run import SubjectRefs
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


class _SellerRoleAttioWriter:
    """Adapts `AttioRoleWriter` to `AttioWriterPort`.

    The port is tool-agnostic — `submit.py` knows nothing about seller roles
    — so the per-tool value mapping is resolved here, at the composition
    root, rather than leaking into the use case.
    """

    def __init__(self, writer: AttioRoleWriter) -> None:
        self._writer = writer

    async def write(self, *, tool: str, payload: JsonObject, ai: JsonObject) -> SubjectRefs:
        entry_values = ai.get("entry_values")
        if not isinstance(entry_values, dict):
            entry_values = {}
        return await self._writer.write_seller_role(
            organization_name=payload.get("company") or payload.get("company_name") or "Unknown",
            domain=payload.get("domain"),
            entry_values=entry_values,
        )


def build_valuation_ai() -> ValuationAi:
    return ValuationAi(build_llm(), build_search())


def build_pipelines() -> Pipelines:
    return Pipelines(build_llm())


def build_submission_service(session: AsyncSession) -> SubmissionService:
    """Every tool's pipeline is reachable from the tool name alone, so the
    same service serves a fresh request and a sweeper resume."""
    pipelines = build_pipelines()
    return SubmissionService(
        tool_runs=build_tool_runs(session),
        attio=_SellerRoleAttioWriter(build_role_writer()),
        run_ai=pipelines.run,
        fallback=pipelines.fallback,
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
