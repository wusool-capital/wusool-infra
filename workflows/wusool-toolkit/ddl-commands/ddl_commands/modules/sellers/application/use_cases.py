"""Seller write use cases — mirrors buyers' `use_cases.py` exactly."""

from sqlalchemy.ext.asyncio import async_sessionmaker

from ddl_commands.modules.sellers.infrastructure.repositories import SellerRepository
from ddl_commands.shared.database.organization_repository import OrganizationRepository
from wusool_db.models import SellerRole


class SellerNotFoundError(Exception):
    pass


class SellerAlreadyExistsError(Exception):
    pass


class UpdateSellerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self,
        seller_role_id: str,
        fields: dict,
        *,
        org_attio_id: str | None = None,
        org_fields: dict | None = None,
    ) -> SellerRole:
        """Writes the role's own fields and, if `org_fields` is given, the
        parent `organizations` row's fields, in one transaction — an
        `/edit-seller` submission can touch both. Called only after the
        corresponding Attio write(s) already succeeded (see
        `ddl_commands/modules/slack/handlers/actions.py`) — this never talks
        to Attio itself.
        """
        async with self._sessionmaker() as session:
            async with session.begin():
                repo = SellerRepository(session)
                role = await repo.get_by_id(seller_role_id)
                if role is None:
                    raise SellerNotFoundError(seller_role_id)
                updated = await repo.update(seller_role_id, **fields) if fields else role
                if org_fields and org_attio_id:
                    await OrganizationRepository(session).update(org_attio_id, **org_fields)
        assert updated is not None
        return updated


class CreateSellerUseCase:
    def __init__(self, sessionmaker: async_sessionmaker) -> None:
        self._sessionmaker = sessionmaker

    async def execute(
        self,
        *,
        org_attio_id: str,
        is_new_org: bool,
        org_name: str | None = None,
        org_fields: dict | None = None,
        role_fields: dict,
    ) -> SellerRole:
        """Called only after the corresponding Attio write(s) already
        succeeded (see `ddl_commands/modules/slack/handlers/actions.py`) —
        this never talks to Attio itself. `org_attio_id` is always Attio's
        own `record_id`, whether from a create that just happened
        (`is_new_org=True`) or an existing org the operator attached to.

        Re-checks for an existing seller role on `org_attio_id` inside this
        same transaction rather than trusting the Slack payload's claim that
        none exists yet — the org-selection step and this submission are two
        separate round trips, and another `/add-seller` could land between
        them. `UNIQUE(org_attio_id)` on `seller_roles` is the final backstop
        either way.
        """
        async with self._sessionmaker() as session:
            async with session.begin():
                org_repo = OrganizationRepository(session)
                if is_new_org:
                    assert org_name is not None
                    await org_repo.create(org_attio_id, org_name, **(org_fields or {}))
                elif org_fields:
                    await org_repo.update(org_attio_id, **org_fields)

                seller_repo = SellerRepository(session)
                if await seller_repo.get_by_org_attio_id(org_attio_id) is not None:
                    raise SellerAlreadyExistsError(org_attio_id)
                role = await seller_repo.create(org_attio_id, **role_fields)
        return role
