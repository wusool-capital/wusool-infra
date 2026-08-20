"""Buyer write use cases. Mirrors the only write pattern matching-engine has
established (its approvals module): the use case owns
`async with sessionmaker() as session: async with session.begin(): ...`; the
repository only does `add`/mutate-attributes/`flush`, never `commit`/
`rollback`. Every write re-loads and re-validates current DB state inside
the transaction — never trusts a Slack payload's claimed state.
"""

from sqlalchemy.ext.asyncio import async_sessionmaker
from wusool_db.models import BuyerRole

from ddl_commands.modules.buyers.infrastructure.repositories import BuyerRepository
from ddl_commands.shared.database.organization_repository import OrganizationRepository


class BuyerNotFoundError(Exception):
    pass


class BuyerAlreadyExistsError(Exception):
    pass


class UpdateBuyerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self,
        buyer_role_id: str,
        fields: dict,
        *,
        org_attio_id: str | None = None,
        org_fields: dict | None = None,
    ) -> BuyerRole:
        """Writes the role's own fields and, if `org_fields` is given, the
        parent `organizations` row's fields, in one transaction — an
        `/edit-buyer` submission can touch both. Called only after the
        corresponding Attio write(s) already succeeded (see
        `ddl_commands/modules/slack/handlers/actions.py`) — this never talks
        to Attio itself.
        """
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = BuyerRepository(session)
                role = await repo.get_by_id(buyer_role_id)
                if role is None:
                    raise BuyerNotFoundError(buyer_role_id)
                updated = await repo.update(buyer_role_id, **fields) if fields else role
                if org_fields and org_attio_id:
                    await OrganizationRepository(session).update(org_attio_id, **org_fields)
        assert updated is not None
        return updated


class CreateBuyerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self,
        *,
        org_attio_id: str,
        entry_id: str,
        is_new_org: bool,
        org_name: str | None = None,
        org_fields: dict | None = None,
        role_fields: dict,
    ) -> BuyerRole:
        """Mirrors `CreateSellerUseCase.execute` exactly, buyer-typed — see
        that docstring for the re-check rationale. `entry_id` is the
        just-created buyer_role list entry's own id.
        """
        async with self._sessionmaker() as session:
            async with session.begin():
                org_repo = OrganizationRepository(session)
                if is_new_org:
                    assert org_name is not None
                    await org_repo.create(org_attio_id, org_name, **(org_fields or {}))
                elif org_fields:
                    await org_repo.update(org_attio_id, **org_fields)

                buyer_repo = BuyerRepository(session)
                if await buyer_repo.get_by_org_attio_id(org_attio_id) is not None:
                    raise BuyerAlreadyExistsError(org_attio_id)
                # `is_active`/`legacy_entry_id` are bot-owned reconciliation
                # state, not operator-editable — set explicitly here, never
                # via `role_fields` (built from `BUYER_ROLE_FIELDS`, the
                # Slack form's editable set).
                role = await buyer_repo.create(
                    org_attio_id, is_active=True, legacy_entry_id=entry_id, **role_fields
                )
        return role
