"""`POST /webhooks/attio` — the one entrypoint for real-time DEV Attio ->
Postgres sync. See `ddl_commands/modules/attio_sync/__init__.py` for the
overall design.

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
from pydantic import ValidationError

from ddl_commands.config import get_settings
from ddl_commands.modules.attio_sync.dispatch import dispatch_event
from ddl_commands.modules.attio_sync.schemas import AttioWebhookEnvelope, AttioWebhookEvent
from ddl_commands.shared.attio.client import get_attio_client
from ddl_commands.shared.attio.signature import verify_attio_signature

router = APIRouter()
_logger = logging.getLogger("ddl_commands.attio_sync")


async def _process(event: AttioWebhookEvent) -> None:
    try:
        await dispatch_event(get_attio_client(), event)
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
