"""Seller write use cases — mirrors buyers' `use_cases.py` exactly."""

from sqlalchemy.ext.asyncio import async_sessionmaker
from wusool_db.models import SellerRole

from ddl_commands.modules.sellers.infrastructure.repositories import SellerRepository
from ddl_commands.shared.database.organization_repository import OrganizationRepository


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
        entry_id: str,
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
        `entry_id` is the just-created seller_role list entry's own id.

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
                    await org_repo.create(
                        org_attio_id, org_name, is_active=True, **(org_fields or {})
                    )
                elif org_fields:
                    await org_repo.update(org_attio_id, **org_fields)

                seller_repo = SellerRepository(session)
                # `org_attio_id` is no longer unique (2026-08-28 migration —
                # see `SellerRole`'s docstring) — an org can hold several
                # role rows, so "already exists" is now an explicit check
                # for an *active* one, not a DB constraint rejecting a
                # second insert. A matching `legacy_entry_id` means this is
                # the very entry this call is about to create, arriving
                # first via the Attio webhook (`sync_seller_role`) racing
                # this same submission — tolerate that and hand back the
                # existing row, rather than raising for what isn't actually
                # a different, pre-existing role.
                existing = await seller_repo.get_by_org_attio_id(org_attio_id)
                if existing is not None and existing.legacy_entry_id != entry_id:
                    raise SellerAlreadyExistsError(org_attio_id)

                if existing is not None:
                    role = existing
                else:
                    # `is_active`/`legacy_entry_id` are bot-owned
                    # reconciliation state, not operator-editable — set
                    # explicitly here, never via `role_fields` (built from
                    # `SELLER_ROLE_FIELDS`, the Slack form's editable set).
                    role = await seller_repo.create(
                        org_attio_id, is_active=True, legacy_entry_id=entry_id, **role_fields
                    )
                    if role.legacy_entry_id != entry_id:
                        # ponytail: no DB constraint enforces "one active
                        # role per org" post-migration (UNIQUE moved to
                        # legacy_entry_id) — the check above plus this
                        # post-insert re-check together close a narrow
                        # TOCTOU window (a role for this org, with a
                        # different entry, created concurrently between
                        # them), not an atomic guarantee. Add a partial
                        # unique index (`org_attio_id` WHERE `is_active`) if
                        # concurrent `/add-seller` submissions on the same
                        # org become a real problem.
                        raise SellerAlreadyExistsError(org_attio_id)
        return role
