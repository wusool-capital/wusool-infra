"""Start and finish a `command_runs` row. Each runs in its own transaction:
`start` must commit before the Attio writes begin, so a command that fails or
lands halfway still leaves a trace."""

from collections.abc import Sequence
from uuid import UUID

from app.modules.ddl_commands.application.base import ServiceBase
from app.modules.ddl_commands.application.ports.command_runs import (
    CommandName,
    CommandStatus,
    InvokedVia,
)


class CommandRunService(ServiceBase):
    async def start_command_run(
        self,
        *,
        command: CommandName,
        invoked_via: InvokedVia,
        requested_by: str | None,
        org_attio_id: str | None = None,
        seller_role_id: UUID | None = None,
        buyer_role_id: UUID | None = None,
    ) -> UUID:
        async with self._uow_factory() as uow:
            return await uow.command_runs.start(
                command=command,
                invoked_via=invoked_via,
                requested_by=requested_by,
                org_attio_id=org_attio_id,
                seller_role_id=seller_role_id,
                buyer_role_id=buyer_role_id,
            )

    async def finish_command_run(
        self,
        run_id: UUID,
        *,
        status: CommandStatus,
        landed: Sequence[str] = (),
        changed_fields: Sequence[str] = (),
        error: str | None = None,
        org_attio_id: str | None = None,
        seller_role_id: UUID | None = None,
        buyer_role_id: UUID | None = None,
    ) -> None:
        async with self._uow_factory() as uow:
            await uow.command_runs.finish(
                run_id,
                status=status,
                landed=landed,
                changed_fields=changed_fields,
                error=error,
                org_attio_id=org_attio_id,
                seller_role_id=seller_role_id,
                buyer_role_id=buyer_role_id,
            )
