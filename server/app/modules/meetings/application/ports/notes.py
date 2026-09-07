"""The `notes`-table persistence seam this module's use cases depend on.
Implemented by
`app.modules.meetings.persistence.notes_repository.NotesRepository`.
"""

from typing import Protocol
from uuid import UUID


class NotesRepositoryPort(Protocol):
    async def create(
        self,
        *,
        note_id: UUID | None,
        organization_id: str | None,
        note_type: str,
        content: str,
        primary_role: str | None,
        buyer_role_id: UUID | None,
        seller_role_id: UUID | None,
    ) -> UUID: ...
