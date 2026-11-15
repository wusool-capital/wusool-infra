"""Composition root: the one `CrmService` the API shares."""

from functools import lru_cache

from app.modules.crm.application.service import CrmService
from app.modules.crm.persistence.database import get_sessionmaker
from app.modules.crm.persistence.roles_repository import PostgresRolesRepository
from app.modules.crm.providers.ddl_commands_writer import DdlCommandsRoleWriter


@lru_cache
def crm_service() -> CrmService:
    return CrmService(PostgresRolesRepository(get_sessionmaker()), DdlCommandsRoleWriter())
