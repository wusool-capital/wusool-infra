"""Buyer write use cases. Mirrors the only write pattern matching-engine has
established (its approvals module): the use case owns
`async with sessionmaker() as session: async with session.begin(): ...`; the
repository only does `add`/mutate-attributes/`flush`, never `commit`/
`rollback`. Every write re-loads and re-validates current DB state inside
the transaction — never trusts a Slack payload's claimed state.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.modules.buyers.infrastructure.models import BuyerRole
from app.modules.buyers.infrastructure.repositories import BuyerRepository


class BuyerNotFoundError(Exception):
    pass


class BuyerAlreadyRemovedError(Exception):
    """Raised when: (a) an edit is attempted on a removed row without
    `restore=True` — shouldn't happen via the normal Slack flow, since the
    handler always knows the row's removed state before calling this, but
    stays a hard guard against a caller bug; or (b) removing an
    already-removed row (never a valid action).
    """


class UpdateBuyerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self,
        buyer_role_id: str,
        fields: dict,
        actor_user_id: str,
        *,
        restore: bool = False,
    ) -> BuyerRole:
        """Doubles as the restore path (§5's checkbox-gated edit flow is what
        makes this safe to call with `restore=True`): clears `removed_at`
        and applies the field changes in the same write.
        """
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = BuyerRepository(session)
                role = await repo.get_by_id(buyer_role_id)
                if role is None:
                    raise BuyerNotFoundError(buyer_role_id)
                if role.removed_at is not None and not restore:
                    raise BuyerAlreadyRemovedError(buyer_role_id)
                if restore:
                    fields = {**fields, "removed_at": None}
                updated = await repo.update(buyer_role_id, actor_user_id, **fields)
        assert updated is not None
        return updated


class RemoveBuyerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(self, buyer_role_id: str, actor_user_id: str) -> BuyerRole:
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = BuyerRepository(session)
                role = await repo.get_by_id(buyer_role_id)
                if role is None:
                    raise BuyerNotFoundError(buyer_role_id)
                if role.removed_at is not None:
                    raise BuyerAlreadyRemovedError(buyer_role_id)
                updated = await repo.remove(buyer_role_id, actor_user_id)
        assert updated is not None
        return updated
