"""Builds the `activities` event for a seller/buyer add or edit, so the four
write use cases share one shape."""

from collections.abc import Iterable
from uuid import UUID

from app.modules.activities import (
    ActivityEvent,
    EventType,
    ProfileWritePayload,
    SubjectType,
)
from app.modules.ddl_commands.application.write_context import WriteContext


def profile_write_event(
    *,
    subject_type: SubjectType,
    event_type: EventType,
    role_id: UUID,
    entry_id: str | None,
    context: WriteContext,
    changed_fields: Iterable[str],
    is_new_org: bool = False,
    idempotency_key: str | None = None,
) -> ActivityEvent:
    return ActivityEvent(
        subject_type=subject_type,
        event_type=event_type,
        source=context.source,
        actor=context.actor,
        payload=ProfileWritePayload(
            changed_fields=tuple(sorted(changed_fields)), is_new_org=is_new_org
        ),
        subject_attio_id=entry_id,
        subject_uuid=role_id,
        outcome="succeeded",
        idempotency_key=idempotency_key,
        command_run_id=context.command_run_id,
    )
