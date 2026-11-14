"""The persistence interface for the `command_runs` ledger — implemented by
`persistence/repositories/command_runs_repository.py`. Subject ids are
optional and the implementation drops any that has no Postgres row yet, so a
stale or not-yet-mirrored id can never fail the ledger write.
"""

from collections.abc import Sequence
from typing import Literal, Protocol
from uuid import UUID

CommandName = Literal["add_seller", "add_buyer", "edit_seller", "edit_buyer"]
InvokedVia = Literal["slack", "discovery", "mcp"]
CommandStatus = Literal["running", "succeeded", "failed", "partial"]


class CommandRunRepositoryPort(Protocol):
    async def start(
        self,
        *,
        command: CommandName,
        invoked_via: InvokedVia,
        requested_by: str | None,
        org_attio_id: str | None = None,
        seller_role_id: UUID | None = None,
        buyer_role_id: UUID | None = None,
    ) -> UUID: ...

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
    ) -> None: ...
