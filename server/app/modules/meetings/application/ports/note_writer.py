"""The Attio note-push seam `PublishMixin` depends on. Structurally
satisfied by `providers.attio.note_writer.AttioNoteWriter` without this
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
        organization_attio_id: str,
        content: str,
        created_at: datetime,
        object_slug: str,
    ) -> UUID | None: ...
