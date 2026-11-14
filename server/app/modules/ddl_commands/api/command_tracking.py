"""Best-effort `command_runs` bookkeeping around the Attio-first write paths.

The ledger exists to leave a trace when a command fails or lands halfway, so
it must never be the reason a command fails: a failed start or finish is
logged and the write carries on.
"""

import asyncio
import logging
from collections.abc import AsyncIterator, Sequence
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from uuid import UUID

from app.modules.activities import ActivityActor, ActivitySource
from app.modules.ddl_commands.api.dependencies import ddl_commands_service
from app.modules.ddl_commands.api.write_errors import PartialWriteError
from app.modules.ddl_commands.application.ports.command_runs import (
    CommandName,
    CommandStatus,
    InvokedVia,
)
from app.modules.ddl_commands.application.service import DdlCommandsService
from app.modules.ddl_commands.application.write_context import WriteContext
from app.modules.utilities.domain.safe_errors import describe_error

logger = logging.getLogger(__name__)

_MAX_ERROR_CHARS = 500


@dataclass
class CommandTracker:
    """What a write body tells the ledger as it learns it."""

    run_id: UUID | None
    context: WriteContext
    org_attio_id: str | None = None
    seller_role_id: UUID | None = None
    buyer_role_id: UUID | None = None
    changed_fields: list[str] = field(default_factory=list)
    # Shared with the write body, which appends as each Attio write lands.
    landed: list[str] = field(default_factory=list)


def uuid_or_none(value: str | None) -> UUID | None:
    if value is None:
        return None
    try:
        return UUID(value)
    except ValueError:
        return None


# Type, never the message: a database or Attio error can quote row values.
def _error_text(exc: BaseException) -> str:
    return describe_error(exc)[:_MAX_ERROR_CHARS]


async def _finish(
    service: DdlCommandsService,
    tracker: CommandTracker,
    status: CommandStatus,
    *,
    landed: Sequence[str] = (),
    error: str | None = None,
) -> None:
    if tracker.run_id is None:
        return
    if status != "succeeded":
        logger.warning(
            "command_run_%s run_id=%s landed=%d error=%s",
            status,
            tracker.run_id,
            len(landed),
            error,
        )
    try:
        await service.finish_command_run(
            tracker.run_id,
            status=status,
            landed=landed,
            changed_fields=tracker.changed_fields,
            error=error,
            org_attio_id=tracker.org_attio_id,
            seller_role_id=tracker.seller_role_id,
            buyer_role_id=tracker.buyer_role_id,
        )
    except Exception:
        logger.exception("command_run_finish_failed run_id=%s", tracker.run_id)


@asynccontextmanager
async def track_command(
    command: CommandName,
    *,
    invoked_via: InvokedVia,
    requested_by: str | None,
    org_attio_id: str | None = None,
    seller_role_id: UUID | None = None,
    buyer_role_id: UUID | None = None,
) -> AsyncIterator[CommandTracker]:
    service = ddl_commands_service()
    run_id: UUID | None = None
    try:
        run_id = await service.start_command_run(
            command=command,
            invoked_via=invoked_via,
            requested_by=requested_by,
            org_attio_id=org_attio_id,
            seller_role_id=seller_role_id,
            buyer_role_id=buyer_role_id,
        )
    except Exception:
        logger.exception("command_run_start_failed command=%s", command)

    if invoked_via == "discovery":
        actor, source = ActivityActor.system("discovery"), ActivitySource.DISCOVERY
    elif invoked_via == "mcp":
        # MCP calls carry the signed-in person's Slack user id.
        actor, source = ActivityActor.slack(requested_by), ActivitySource.MCP
    else:
        actor, source = ActivityActor.slack(requested_by), ActivitySource.SLACK
    tracker = CommandTracker(run_id=run_id, context=WriteContext(actor, source, run_id))

    try:
        yield tracker
    except PartialWriteError as exc:
        partial_status: CommandStatus = "partial" if exc.landed else "failed"
        await _finish(
            service, tracker, partial_status, landed=exc.landed, error=_error_text(exc.cause)
        )
        raise
    except asyncio.CancelledError:
        # Shielded so a second cancel cannot strand the row at "running".
        status = "partial" if tracker.landed else "failed"
        await asyncio.shield(
            _finish(
                service,
                tracker,
                status,
                landed=tracker.landed,
                error="cancelled before the write finished",
            )
        )
        raise
    except Exception as exc:
        # Not a PartialWriteError, yet earlier Attio writes may have landed.
        status = "partial" if tracker.landed else "failed"
        await _finish(service, tracker, status, landed=tracker.landed, error=_error_text(exc))
        raise
    else:
        await _finish(service, tracker, "succeeded")
