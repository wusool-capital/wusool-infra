"""Seller write use cases — mirrors buyers' `use_cases.py` exactly. No
`CreateSellerUseCase`/`SellerAlreadyExistsError` yet — `/add-seller` is
deliberately out of scope for this pass (pending the org-creation decision).
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from ddl_commands.modules.sellers.infrastructure.models import SellerRole
from ddl_commands.modules.sellers.infrastructure.repositories import SellerRepository


class SellerNotFoundError(Exception):
    pass


class SellerAlreadyRemovedError(Exception):
    """Raised when: (a) an edit is attempted on a removed row without
    `restore=True`; or (b) removing an already-removed row."""


class UpdateSellerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self,
        seller_role_id: str,
        fields: dict,
        actor_user_id: str,
        *,
        restore: bool = False,
    ) -> SellerRole:
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = SellerRepository(session)
                role = await repo.get_by_id(seller_role_id)
                if role is None:
                    raise SellerNotFoundError(seller_role_id)
                if role.removed_at is not None and not restore:
                    raise SellerAlreadyRemovedError(seller_role_id)
                if restore:
                    fields = {**fields, "removed_at": None}
                updated = await repo.update(seller_role_id, actor_user_id, **fields)
        assert updated is not None
        return updated


class RemoveSellerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(self, seller_role_id: str, actor_user_id: str) -> SellerRole:
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = SellerRepository(session)
                role = await repo.get_by_id(seller_role_id)
                if role is None:
                    raise SellerNotFoundError(seller_role_id)
                if role.removed_at is not None:
                    raise SellerAlreadyRemovedError(seller_role_id)
                updated = await repo.remove(seller_role_id, actor_user_id)
        assert updated is not None
        return updated
