"""Composition root for this module's own FastAPI app: health/readiness,
exception handling, logging, and the Slack ASGI mount. Slack is the only
product interface — no public REST endpoints for buyer/seller data. Also
holds the `build_*` factory functions `api/dependencies.py` calls instead
of constructing concrete persistence classes inline.

`create_app()` exists for running this module in isolation (its own test
suite, `uv run --package ddl_commands ...`-style standalone use) — the
actually-deployed process is `server/main.py`, which merges both modules'
Slack handlers onto one `AsyncApp` instead of calling this.
"""

import logging
from functools import lru_cache

from fastapi import FastAPI, Request, Response
from fastapi.responses import JSONResponse
from slack_bolt.adapter.fastapi.async_handler import AsyncSlackRequestHandler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.modules.ddl_commands.application.ports.attio_sync import AttioRegistryPort
from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWorkFactory
from app.modules.ddl_commands.config import get_settings
from app.modules.ddl_commands.persistence.attio_sync import AttioSyncRepository
from app.modules.ddl_commands.persistence.database import (
    check_database_connectivity,
    import_all_models,
)
from app.modules.ddl_commands.persistence.repositories.buyers_repository import BuyerRepository
from app.modules.ddl_commands.persistence.repositories.sellers_repository import SellerRepository
from app.modules.ddl_commands.persistence.unit_of_work import SqlAlchemyDdlCommandsUnitOfWork
from app.modules.ddl_commands.providers.attio_registry import AttioRegistry
from app.modules.organizations import OrganizationRepository
from app.modules.utilities.api.handlers import register_exception_handlers
from app.modules.utilities.domain.logging import configure_logging

_logger = logging.getLogger("app.modules.ddl_commands.bootstrap")


def build_buyer_repository(session: AsyncSession) -> BuyerRepository:
    return BuyerRepository(session)


def build_seller_repository(session: AsyncSession) -> SellerRepository:
    return SellerRepository(session)


def build_organization_repository(session: AsyncSession) -> OrganizationRepository:
    return OrganizationRepository(session)


def build_ddl_commands_unit_of_work_factory(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> DdlCommandsUnitOfWorkFactory:
    def _factory() -> SqlAlchemyDdlCommandsUnitOfWork:
        return SqlAlchemyDdlCommandsUnitOfWork(sessionmaker)

    return _factory


def build_attio_sync_repository() -> AttioSyncRepository:
    return AttioSyncRepository()


def build_attio_registry() -> AttioRegistryPort:
    return AttioRegistry()


def create_app() -> FastAPI:
    # Local import: `api.slack.bolt_app` -> `api.slack.handlers` ->
    # `api.dependencies`, which imports this module's `build_*` factories —
    # a module-level import here would cycle. Safe deferred to call time:
    # by the time `create_app()` actually runs, every module is already
    # fully loaded.
    from app.modules.ddl_commands.api.slack.bolt_app import get_bolt_app

    settings = get_settings()
    configure_logging(settings.log_level)
    import_all_models()

    app = FastAPI(title="DDL Commands — Buyer/Seller Profile Editor")
    register_exception_handlers(app)

    @app.get("/health")
    async def health() -> dict[str, str]:
        """Liveness check. Does not touch the database."""
        return {"status": "ok"}

    async def _readiness() -> JSONResponse:
        """Readiness check. Confirms database connectivity via `SELECT 1`."""
        try:
            await check_database_connectivity()
        except Exception:
            _logger.error("Readiness check failed", exc_info=True)
            return JSONResponse(status_code=503, content={"status": "unavailable"})
        return JSONResponse(status_code=200, content={"status": "ready"})

    @app.get("/readiness")
    async def readiness() -> JSONResponse:
        return await _readiness()

    @app.get("/ready")
    async def ready() -> JSONResponse:
        """Alias for `/readiness`."""
        return await _readiness()

    @lru_cache
    def _slack_request_handler() -> AsyncSlackRequestHandler:
        return AsyncSlackRequestHandler(get_bolt_app())

    @app.post("/slack/events")
    async def slack_events(req: Request) -> Response:
        """The Slack callback endpoint. Signature verification happens
        inside Bolt via `SLACK_SIGNING_SECRET` — never trust a payload
        without it.
        """
        return await _slack_request_handler().handle(req)

    return app
