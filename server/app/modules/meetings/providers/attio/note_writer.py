"""Pushes a meeting summary to Attio's "note" object as a best-effort side
write. `AttioNoteWriter.push_note` must never fail the caller's meeting: any
Attio error is caught, logged, and turned into `None` so a broken Attio
integration can't break meeting summarization. Postgres is not written
here -- the caller decides what `None` means (skip Attio, insert
Postgres-only with a fresh id), and whether to call this at all (this
class writes to the `note` object unconditionally).
"""

from __future__ import annotations

import logging
from datetime import datetime
from uuid import UUID

from app.modules.attio import AttioClient, get_attio_client

logger = logging.getLogger(__name__)

# One SOURCE workspace, one note object. Was ATTIO_NOTE_OBJECT_SLUG, which
# existed only so DEV — where the object did not exist — could skip note
# sync by leaving it unset.
_NOTE_OBJECT_SLUG = "note"


class AttioNoteWriter:
    def __init__(self, client: AttioClient | None = None, *, is_test: bool) -> None:
        """`is_test` is which half of the single shared SOURCE workspace this
        process owns. Taken here rather than as a `push_note` argument: that
        method is the `NoteWriterPort` surface, and threading the flag
        through it would put an Attio-workspace concept into
        `meetings/application/`, which has no business knowing about one.
        """
        self._client = client or get_attio_client()
        self._is_test = is_test

    async def push_note(
        self,
        *,
        organization_attio_id: str | None,
        content: str,
        created_at: datetime,
        primary_role: str | None,
        buyer_role_entry_id: str | None,
        seller_role_entry_id: str | None,
    ) -> UUID | None:
        """POST a "Meeting" note to Attio's `note` object, linked to
        `organization_attio_id`. Attribute slugs (`organization_id`,
        `note_type`, `content`, `note_created_at`) match the ones
        `ddl_commands.persistence.attio_sync._note_params` already reads
        back -- `note_created_at`, not `created_at`, since Attio reserves
        `created_at` as a protected system attribute on every custom object.

        `organization_attio_id` is `None` for a meeting with no resolved
        company (internal/general/investor, or a company that never
        resolved to an Attio org) — the `organization_id` key is omitted
        entirely rather than sent as an empty/null reference, matching how
        `buyer_role_id`/`seller_role_id` are also omitted when there is no
        role to link.

        `buyer_role_entry_id`/`seller_role_entry_id` are the target role
        row's `legacy_entry_id` (Attio's list *entry* id — record-reference
        targets Objects, not List entries, so these attributes are plain
        text, matching `ddl_commands.persistence.attio_sync._note_params`'s
        read side). Never send both: the caller resolves at most one, from
        the meeting's primary role.

        Returns the created record's id so the caller can reuse it verbatim
        as `notes.id` (`ddl_commands`' `_NOTE_UPSERT` is `ON CONFLICT (id)`
        against this same Attio-assigned id), or `None` on any Attio
        failure.
        """
        values: dict[str, object] = {
            "note_type": "Meeting",
            "content": content,
            "note_created_at": created_at.isoformat(),
            # One SOURCE workspace serves both environments; a note written
            # without this is invisible in the UI of both (Attio's checkbox
            # filter has no "is empty").
            "is_test": self._is_test,
        }
        if organization_attio_id is not None:
            # Record-reference attribute: Attio's write shape needs
            # target_object alongside target_record_id -- the read-side
            # shape (domain/records.py's AttioValueEntry.target_record_id)
            # only carries the id back, not the object it points to.
            values["organization_id"] = [
                {"target_object": "organizations", "target_record_id": organization_attio_id}
            ]
        if primary_role is not None:
            values["primary_role"] = primary_role
        if buyer_role_entry_id is not None:
            values["buyer_role_id"] = buyer_role_entry_id
        if seller_role_entry_id is not None:
            values["seller_role_id"] = seller_role_entry_id
        try:
            response = await self._client.post(
                f"/objects/{_NOTE_OBJECT_SLUG}/records", {"data": {"values": values}}
            )
            return UUID(response["data"]["id"]["record_id"])
        except Exception as exc:  # noqa: BLE001 - must never raise into the caller's meeting flow
            logger.warning(
                "note_push_failed error=%s",
                exc,
                extra={"error": str(exc)},
            )
            return None
