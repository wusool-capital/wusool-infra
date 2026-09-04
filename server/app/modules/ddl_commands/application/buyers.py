"""Buyer resolution semantics and write use cases.

Resolution: the repository owns lookup mechanics; this service owns what to
do with 0/1/many results — kept out of the Slack handler entirely. Every
non-empty result always populates `candidates` (length 1 for a single
match) — the Slack layer always shows a "choose the right buyer" modal, even
for one strong match, mirroring matching-engine's `/find-match` convention.

Writes use a `DdlCommandsUnitOfWork` (mirrors `matching_engine`'s own
`MatchingUnitOfWork`): the use case owns `async with self._uow_factory() as
uow: ...`, which commits on clean exit / rolls back on exception; the
repository only does `add`/mutate-attributes/`flush`, never
`commit`/`rollback`. Every write re-loads and re-validates current DB state
inside the transaction — never trusts a Slack payload's claimed state.
"""

from dataclasses import dataclass
from typing import Literal

from app.models import BuyerRole
from app.modules.ddl_commands.application.errors import (
    BuyerAlreadyExistsError,
    BuyerNotFoundError,
)
from app.modules.ddl_commands.application.ports.buyers import BuyerRepositoryPort
from app.modules.ddl_commands.application.ports.unit_of_work import DdlCommandsUnitOfWorkFactory
from app.modules.utilities.domain.json_types import JsonObject

ResolutionStatus = Literal["none", "single", "multiple"]


@dataclass(frozen=True)
class BuyerResolution:
    """`candidates` are raw ORM rows, not `BuyerSummary` — this bot has no
    domain layer (see `resolve_by_id`'s docstring), and application code
    must not import the api-layer Pydantic schema; the ORM->schema
    conversion happens in `api/dependencies.py`, right where the schema is
    actually used.
    """

    status: ResolutionStatus
    candidates: list[BuyerRole] | None = None


class BuyerResolutionService:
    def __init__(self, buyer_repository: BuyerRepositoryPort) -> None:
        self._buyers = buyer_repository

    async def resolve(self, buyer_name: str) -> BuyerResolution:
        matches = await self._buyers.search_by_organization_name(buyer_name)
        if not matches:
            return BuyerResolution(status="none")

        status: ResolutionStatus = "single" if len(matches) == 1 else "multiple"
        return BuyerResolution(status=status, candidates=matches)

    async def resolve_by_id(self, buyer_role_id: str) -> BuyerRole | None:
        """Used after a Slack buyer-selection modal submission. Returns the
        ORM row directly (organization eager-loaded) — this bot has no
        matching pipeline, so there's no need for a separate domain value
        object/mapper layer the way matching-engine has.
        """
        return await self._buyers.get_with_organization(buyer_role_id)


class UpdateBuyerUseCase:
    def __init__(self, uow_factory: DdlCommandsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        buyer_role_id: str,
        fields: JsonObject,
        *,
        org_attio_id: str | None = None,
        org_fields: JsonObject | None = None,
    ) -> BuyerRole:
        """Writes the role's own fields and, if `org_fields` is given, the
        parent `organizations` row's fields, in one transaction — an
        `/edit-buyer` submission can touch both. Called only after the
        corresponding Attio write(s) already succeeded (see
        `api/slack/handlers/actions.py`) — this never talks to Attio itself.
        """
        async with self._uow_factory() as uow:
            role = await uow.buyers.get_by_id(buyer_role_id)
            if role is None:
                raise BuyerNotFoundError(buyer_role_id)
            updated = await uow.buyers.update(buyer_role_id, **fields) if fields else role
            if org_fields and org_attio_id:
                await uow.organizations.update(org_attio_id, **org_fields)
        assert updated is not None
        return updated


class CreateBuyerUseCase:
    def __init__(self, uow_factory: DdlCommandsUnitOfWorkFactory) -> None:
        self._uow_factory = uow_factory

    async def execute(
        self,
        *,
        org_attio_id: str,
        entry_id: str,
        is_new_org: bool,
        org_name: str | None = None,
        org_fields: JsonObject | None = None,
        role_fields: JsonObject,
    ) -> BuyerRole:
        """Mirrors `CreateSellerUseCase.execute` exactly, buyer-typed — see
        that docstring for the re-check rationale. `entry_id` is the
        just-created buyer_role list entry's own id.
        """
        async with self._uow_factory() as uow:
            if is_new_org:
                assert org_name is not None
                await uow.organizations.create(
                    org_attio_id, org_name, is_active=True, **(org_fields or {})
                )
            elif org_fields:
                await uow.organizations.update(org_attio_id, **org_fields)

            # Serializes concurrent /add-buyer for this org: the check below
            # is application-level, so without this both could pass it.
            await uow.organizations.lock(org_attio_id)

            # `org_attio_id` is no longer unique (2026-08-28 migration — see
            # `BuyerRole`'s docstring), so "already exists" is an explicit
            # check for an active role, not a DB constraint. A matching
            # `legacy_entry_id` means the Attio webhook (`sync_buyer_role`)
            # raced this same submission and already created this entry --
            # tolerate that and return the existing row instead of raising.
            existing = await uow.buyers.get_by_org_attio_id(org_attio_id)
            if existing is not None and existing.legacy_entry_id != entry_id:
                raise BuyerAlreadyExistsError(org_attio_id)

            if existing is not None:
                role = existing
            else:
                # `is_active`/`legacy_entry_id` are bot-owned reconciliation
                # state, not operator-editable -- set explicitly, never via
                # `role_fields` (the Slack form's editable set).
                role = await uow.buyers.create(
                    org_attio_id, is_active=True, legacy_entry_id=entry_id, **role_fields
                )
                if role.legacy_entry_id != entry_id:
                    # Backstop for writers that don't take the org lock --
                    # `sync_buyer_role` can land a row for this org between
                    # the check above and this insert.
                    #
                    # ponytail: a partial unique index (org_attio_id WHERE
                    # is_active) would cover those too, but Postgres can't
                    # defer a partial unique index and `sync_buyer_role`
                    # promotes an org's new winner before demoting the old
                    # one in one transaction -- it needs that loop reordered
                    # losers-first first.
                    raise BuyerAlreadyExistsError(org_attio_id)
        return role
