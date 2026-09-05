"""Pushes a meeting summary to Attio's "note" object as a best-effort side
write. `AttioNoteWriter.push_note` must never fail the caller's meeting: any
Attio error is caught, logged, and turned into `None` so a broken Attio
integration can't break meeting summarization. Postgres is not written
here -- the caller decides what `None` means (skip Attio, insert
Postgres-only with a fresh id), and whether to call this at all (this
class doesn't gate on `settings.attio_note_object_slug` being set).
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from app.modules.attio import AttioClient, get_attio_client

logger = logging.getLogger(__name__)


class AttioNoteWriter:
    def __init__(self, client: AttioClient | None = None) -> None:
        self._client = client or get_attio_client()

    async def push_note(
        self,
        *,
        organization_attio_id: str,
        content: str,
        created_at: datetime,
        object_slug: str,
    ) -> UUID | None:
        """POST a "Meeting" note to Attio's `object_slug` object, linked to
        `organization_attio_id`. Attribute slugs (`organization_id`,
        `note_type`, `content`, `note_created_at`) match the ones
        `ddl_commands.persistence.attio_sync._note_params` already reads
        back -- `note_created_at`, not `created_at`, since Attio reserves
        `created_at` as a protected system attribute on every custom object.

        Returns the created record's id so the caller can reuse it verbatim
        as `notes.id` (`ddl_commands`' `_NOTE_UPSERT` is `ON CONFLICT (id)`
        against this same Attio-assigned id), or `None` on any Attio
        failure.
        """
        values = {
            # Record-reference attribute: Attio's write shape needs
            # target_object alongside target_record_id -- the read-side
            # shape (domain/records.py's AttioValueEntry.target_record_id)
            # only carries the id back, not the object it points to.
            "organization_id": [
                {"target_object": "organizations", "target_record_id": organization_attio_id}
            ],
            "note_type": "Meeting",
            "content": content,
            "note_created_at": created_at.isoformat(),
        }
        try:
            response = await self._client.post(
                f"/objects/{object_slug}/records", {"data": {"values": values}}
            )
            return UUID(response["data"]["id"]["record_id"])
        except Exception as exc:  # noqa: BLE001 - must never raise into the caller's meeting flow
            logger.warning(
                "note_push_failed object_slug=%s error=%s",
                object_slug,
                exc,
                extra={"object_slug": object_slug, "error": str(exc)},
            )
            return None
