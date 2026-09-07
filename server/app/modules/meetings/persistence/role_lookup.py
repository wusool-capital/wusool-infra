"""Adapter implementing `application.ports.roles.RoleLookupPort` by querying
`app.models.BuyerRole`/`SellerRole` directly. `buyer_roles`/`seller_roles`
have no owning module — only `ddl_commands`'s write-side repositories, and
`ddl_commands` is not a full-access peer module (`server/tests/
test_architecture.py`'s `_FULL_ACCESS_MODULES`) — so this queries the shared
ORM models from `persistence/`, the same place `notes_repository.py` and
`meetings_repository.py` already do for `Note`/`Meeting`.
"""

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, SellerRole
from app.modules.meetings.domain.role_ref import ActiveRoleRef
from app.modules.meetings.persistence.mappers import (
    to_active_buyer_role_ref,
    to_active_seller_role_ref,
)


class RoleLookup:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_active_buyer_role(self, org_attio_id: str) -> ActiveRoleRef | None:
        stmt = (
            select(BuyerRole)
            .where(BuyerRole.org_attio_id == org_attio_id, BuyerRole.is_active.is_(True))
            # `id DESC` breaks ties: `created_at` defaults to `now()`, which
            # is transaction-scoped, so rows written by one bulk sync pass
            # can share an identical timestamp.
            .order_by(BuyerRole.created_at.desc(), BuyerRole.id.desc())
            .limit(1)
        )
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_active_buyer_role_ref(role) if role is not None else None

    async def get_active_seller_role(self, org_attio_id: str) -> ActiveRoleRef | None:
        stmt = (
            select(SellerRole)
            .where(SellerRole.org_attio_id == org_attio_id, SellerRole.is_active.is_(True))
            .order_by(SellerRole.created_at.desc(), SellerRole.id.desc())
            .limit(1)
        )
        role = (await self._session.execute(stmt)).scalar_one_or_none()
        return to_active_seller_role_ref(role) if role is not None else None
