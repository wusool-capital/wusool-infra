"""Port for Organization persistence. Returns the shared ORM `Organization`
model directly, not a domain entity — mirrors `ddl_commands`' own
established convention (no matching pipeline, so no value-object/mapper
layer is warranted): every consumer today (Slack org-selection/search
modals) immediately reads ORM attributes and eager-loaded
`seller_roles`/`buyer_roles`, not business logic that needs a
framework-free representation.
"""

from typing import Any, Protocol

from app.models import Organization


class OrganizationRepositoryPort(Protocol):
    async def get_by_id(self, attio_id: str) -> Organization | None: ...
    async def get_by_id_with_roles(self, attio_id: str) -> Organization | None: ...
    async def search_by_name(self, term: str, limit: int = 10) -> list[Organization]: ...
    async def create(self, attio_id: str, name: str, **fields: Any) -> Organization: ...
    async def update(self, attio_id: str, **fields: Any) -> Organization | None: ...
