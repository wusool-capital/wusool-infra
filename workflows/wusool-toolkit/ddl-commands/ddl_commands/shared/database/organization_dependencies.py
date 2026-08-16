"""Session-managed entry point for organization search, so `/add-seller`/
`/add-buyer` don't construct a repository/session themselves — mirrors
`ddl_commands/modules/sellers/dependencies.py`'s shape.
"""

from ddl_commands.shared.database import get_sessionmaker
from ddl_commands.shared.database.models.organization import Organization
from ddl_commands.shared.database.organization_repository import OrganizationRepository


async def search_organizations(term: str) -> list[Organization]:
    async with get_sessionmaker()() as session:
        return await OrganizationRepository(session).search_by_name(term)


async def resolve_organization(attio_id: str) -> Organization | None:
    async with get_sessionmaker()() as session:
        return await OrganizationRepository(session).get_by_id_with_roles(attio_id)
