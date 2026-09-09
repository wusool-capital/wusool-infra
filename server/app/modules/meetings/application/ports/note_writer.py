"""The Attio note-push seam `PublishMixin` depends on. Structurally
satisfied by `app.modules.attio`'s `AttioNoteWriter` without this
module's `application/` layer ever importing `providers/` directly (the
architecture fitness test in `tests/test_architecture.py` forbids it) —
`bootstrap.py` constructs the concrete `AttioNoteWriter` and hands it to
`ServiceBase` typed as this Protocol.
"""

from datetime import datetime
from typing import Protocol
from uuid import UUID


class NoteWriterPort(Protocol):
    async def push_note(
        self,
        *,
        organization_attio_id: str | None,
        content: str,
        created_at: datetime,
        primary_role: str | None,
        buyer_role_entry_id: str | None,
        seller_role_entry_id: str | None,
    ) -> UUID | None: ...
