"""Adapter implementing `application.ports.organizations.OrganizationLookupPort`
by wrapping the shared `organizations.OrganizationRepository` — allowed since
`organizations` is a documented full-access peer module (see its own
`__init__.py`).
"""

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.domain.organization_ref import OrganizationRef
from app.modules.meetings.persistence.mappers import to_organization_ref
from app.modules.organizations import OrganizationRepository


class OrganizationLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._repo = OrganizationRepository(session)

    async def get_by_id(self, attio_id: str) -> OrganizationRef | None:
        org = await self._repo.get_by_id(attio_id)
        return to_organization_ref(org) if org is not None else None

    async def search_by_name(self, term: str, limit: int) -> list[OrganizationRef]:
        orgs = await self._repo.search_by_name(term, limit)
        return [to_organization_ref(org) for org in orgs]
