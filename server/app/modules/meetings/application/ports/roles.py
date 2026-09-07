"""The active-buyer/seller-role lookup seam `PublishMixin` depends on to
link a meeting note to the org's current mandate. `buyer_roles`/
`seller_roles` have no owning module — only `ddl_commands`'s write-side
repositories, and `ddl_commands` is not a full-access peer module — so this
module queries the shared ORM models directly from its own `persistence/`,
behind this Port, the same shape `organization_lookup.py` uses for the
(module-owned) `organizations` repository.

Implemented by `app.modules.meetings.persistence.role_lookup.RoleLookup`.
"""

from typing import Protocol

from app.modules.meetings.domain.role_ref import ActiveRoleRef


class RoleLookupPort(Protocol):
    async def get_active_buyer_role(self, org_attio_id: str) -> ActiveRoleRef | None: ...

    async def get_active_seller_role(self, org_attio_id: str) -> ActiveRoleRef | None: ...
