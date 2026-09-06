"""The narrow organization-lookup seam this module needs from the shared
`organizations` module. Keeping this Port here — rather than importing
`app.modules.organizations` directly from `application/` — keeps this
module's dependency on `organizations` declared through its own Port, the
same way `matching_engine` keeps its own Port for `meetings` even though the
underlying repository is shared. Implemented by
`app.modules.meetings.persistence.organization_lookup.OrganizationLookup`,
which wraps `organizations.OrganizationRepository`.
"""

from typing import Protocol

from app.modules.meetings.domain.organization_ref import OrganizationRef


class OrganizationLookupPort(Protocol):
    async def get_by_id(self, attio_id: str) -> OrganizationRef | None: ...

    async def search_by_name(self, term: str, limit: int) -> list[OrganizationRef]: ...
