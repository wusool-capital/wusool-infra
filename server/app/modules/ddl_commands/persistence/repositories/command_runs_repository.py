"""The `command_runs` ledger. Flush-only: the unit of work commits.

Subject ids go in as scalar subqueries over the target table, so one with no
Postgres row yet (a stale Slack payload, an org created in Attio whose
Postgres write failed) becomes NULL instead of an FK violation.
"""

from collections.abc import Sequence
from uuid import UUID

from sqlalchemy import ScalarSelect, func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import BuyerRole, CommandRun, Organization, SellerRole
from app.modules.ddl_commands.application.ports.command_runs import (
    CommandName,
    CommandStatus,
    InvokedVia,
)


def _org(attio_id: str | None) -> ScalarSelect[str] | None:
    if attio_id is None:
        return None
    return select(Organization.attio_id).where(Organization.attio_id == attio_id).scalar_subquery()


def _role(
    model: type[SellerRole] | type[BuyerRole], role_id: UUID | None
) -> ScalarSelect[UUID] | None:
    if role_id is None:
        return None
    return select(model.id).where(model.id == role_id).scalar_subquery()


class CommandRunRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def start(
        self,
        *,
        command: CommandName,
        invoked_via: InvokedVia,
        requested_by: str | None,
        org_attio_id: str | None = None,
        seller_role_id: UUID | None = None,
        buyer_role_id: UUID | None = None,
    ) -> UUID:
        result = await self._session.execute(
            insert(CommandRun)
            .values(
                command=command,
                invoked_via=invoked_via,
                requested_by=requested_by,
                status="running",
                org_attio_id=_org(org_attio_id),
                seller_role_id=_role(SellerRole, seller_role_id),
                buyer_role_id=_role(BuyerRole, buyer_role_id),
            )
            .returning(CommandRun.id)
        )
        return result.scalar_one()

    async def finish(
        self,
        run_id: UUID,
        *,
        status: CommandStatus,
        landed: Sequence[str],
        changed_fields: Sequence[str],
        error: str | None,
        org_attio_id: str | None = None,
        seller_role_id: UUID | None = None,
        buyer_role_id: UUID | None = None,
    ) -> None:
        stmt = (
            update(CommandRun)
            .where(CommandRun.id == run_id)
            .values(
                status=status,
                finished_at=func.now(),
                landed=list(landed),
                changed_fields=list(changed_fields),
                error=error,
            )
        )
        # Only overwrite a subject the caller actually resolved; an edit already
        # set its subjects at `start`.
        if org_attio_id is not None:
            stmt = stmt.values(org_attio_id=_org(org_attio_id))
        if seller_role_id is not None:
            stmt = stmt.values(seller_role_id=_role(SellerRole, seller_role_id))
        if buyer_role_id is not None:
            stmt = stmt.values(buyer_role_id=_role(BuyerRole, buyer_role_id))
        await self._session.execute(stmt)
