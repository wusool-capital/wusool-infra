"""The Attio webhook-event envelope shape as plain dataclasses — generic
Attio wire format, not specific to any one module's sync business logic.
`ddl_commands/api/attio_sync.py` validates the inbound JSON as Pydantic and
converts to these before calling into `ddl_commands/application/attio_sync.py`,
so that dispatcher depends on this module's domain, never on an api layer's
Pydantic schemas.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WebhookEventId:
    workspace_id: str | None = None
    object_id: str | None = None
    record_id: str | None = None
    attribute_id: str | None = None
    list_id: str | None = None
    entry_id: str | None = None


@dataclass(frozen=True)
class WebhookEvent:
    event_type: str
    id: WebhookEventId = field(default_factory=WebhookEventId)
