"""Pydantic schemas at this module's external boundary — the inbound Attio
webhook payload itself. Same "schemas at the boundary" convention as
`modules/buyers/schemas.py`/`modules/sellers/schemas.py`: validate once,
here, at the edge, rather than letting `dispatch.py` and the sync functions
work off an untyped `dict` with ad-hoc `.get()` calls.
"""

from pydantic import BaseModel, Field


class AttioWebhookEventId(BaseModel):
    """Which fields are populated depends on `event_type`: `record.*` events
    carry `object_id`/`record_id` (plus `attribute_id` for `.updated`);
    `list-entry.*` events carry `list_id`/`entry_id`. All optional rather
    than shaped per event_type — Attio's webhook reference doesn't guarantee
    a fixed split across every event category (`comment.*`, `task.*`, ...),
    and those are outside this sync's scope anyway (see `dispatch.py`)."""

    workspace_id: str | None = None
    object_id: str | None = None
    record_id: str | None = None
    attribute_id: str | None = None
    list_id: str | None = None
    entry_id: str | None = None


class AttioWebhookEvent(BaseModel):
    """The full inbound `POST /webhooks/attio` payload. `event_type` is the
    only field guaranteed present across every Attio webhook event category —
    see `dispatch.py` for which ones this sync actually acts on."""

    event_type: str
    id: AttioWebhookEventId = Field(default_factory=AttioWebhookEventId)
