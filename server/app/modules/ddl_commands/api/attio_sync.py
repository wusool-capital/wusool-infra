"""The `/webhooks/attio` route, plus the Pydantic schemas validating its
inbound payload — the same "schemas at the boundary" convention as
`api/buyers.py`/`api/sellers.py`: validate once, here, at the edge, rather
than letting `application/attio_sync.py`'s dispatcher work off an untyped
`dict` with ad-hoc `.get()` calls.

Two guards wrap the actual sync logic, both required for a route that's
public and shares a process with the Slack bot (`/slack/events`):

1. Signature verification, first thing — rejects forged requests before they
   can trigger any outbound Attio call or database write, and before an
   unauthenticated caller could ever burn this process's Attio API rate
   limit (shared with `/edit-seller`/`/edit-buyer`/`/add-*`).
2. Acknowledge immediately, then do the actual work in a background task,
   wrapped in a blanket `except` — Attio never waits on the sync itself
   finishing, and nothing this route does can crash the shared process or
   delay the Slack bot's own request handling. A failed sync is logged and
   corrected by the next event touching the same record, or by
   `sync-postgres.ps1`'s nightly safety-net run — never a hang or a 500 that
   competes with Slack's 3-second ack window.
"""

import logging

from fastapi import APIRouter, BackgroundTasks, Request, Response
from pydantic import BaseModel, Field, ValidationError

from app.modules.attio import WebhookEvent, WebhookEventId, get_attio_client
from app.modules.attio.providers.attio.signature import verify_attio_signature
from app.modules.ddl_commands.application.attio_sync import dispatch_event
from app.modules.ddl_commands.bootstrap import build_attio_registry, build_attio_sync_repository
from app.modules.ddl_commands.config import get_settings


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
    """One event within a delivery's `events` array. `event_type` is the
    only field guaranteed present across every Attio webhook event category —
    see `dispatch.py` for which ones this sync actually acts on."""

    event_type: str
    id: AttioWebhookEventId = Field(default_factory=AttioWebhookEventId)


class AttioWebhookEnvelope(BaseModel):
    """The actual top-level shape of every `POST /webhooks/attio` delivery —
    confirmed against a real rejected payload logged 2026-08-18, not just
    Attio's isolated single-event doc examples: `{"webhook_id": ...,
    "events": [...]}`. `events` is a genuine array; one delivery can carry
    more than one event, so every event in it needs dispatching, not just
    the first."""

    webhook_id: str | None = None
    events: list[AttioWebhookEvent] = Field(default_factory=list)


router = APIRouter()
_logger = logging.getLogger("app.modules.ddl_commands.attio_sync")


def _to_domain(event: AttioWebhookEvent) -> WebhookEvent:
    return WebhookEvent(
        event_type=event.event_type,
        id=WebhookEventId(
            workspace_id=event.id.workspace_id,
            object_id=event.id.object_id,
            record_id=event.id.record_id,
            attribute_id=event.id.attribute_id,
            list_id=event.id.list_id,
            entry_id=event.id.entry_id,
        ),
    )


async def _process(event: AttioWebhookEvent) -> None:
    try:
        await dispatch_event(
            build_attio_sync_repository(),
            build_attio_registry(),
            get_attio_client(),
            _to_domain(event),
        )
    except Exception:
        _logger.error("attio webhook sync failed for event %r", event, exc_info=True)


@router.post("/webhooks/attio")
async def attio_webhook(request: Request, background_tasks: BackgroundTasks) -> Response:
    raw_body = await request.body()
    signature = request.headers.get("Attio-Signature")
    if not verify_attio_signature(raw_body, signature, get_settings().attio_webhook_secret):
        return Response(status_code=401)

    try:
        envelope = AttioWebhookEnvelope.model_validate_json(raw_body)
    except ValidationError:
        # Logged in full -- this route sees at most a handful of requests a
        # minute even in a burst, so volume isn't a concern, and seeing
        # exactly what Attio sent is the only way to fix a schema mismatch
        # once, permanently, instead of guessing and redeploying repeatedly.
        # This is exactly how the envelope shape itself was confirmed.
        _logger.error(
            "attio webhook payload failed validation: %s", raw_body.decode(errors="replace")
        )
        return Response(status_code=400)

    for event in envelope.events:
        background_tasks.add_task(_process, event)
    return Response(status_code=200)
