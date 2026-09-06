"""Write access to the shared `notes` table for the meeting-summary pipeline.
`add()`/`flush()` only — never `commit()`/`rollback()`; the caller owns the
transaction boundary.

Implements `application.ports.notes.NotesRepositoryPort`.
"""

from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Note


class NotesRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self, *, note_id: UUID | None, organization_id: str | None, note_type: str, content: str
    ) -> None:
        """`note_id` is supplied when the row must reuse Attio's own record id
        (the note was already pushed to Attio); left `None` lets the column's
        own `gen_random_uuid()` server default apply (Postgres-only case, no
        Attio push).
        """
        kwargs = {"id": note_id} if note_id is not None else {}
        note = Note(organization_id=organization_id, note_type=note_type, content=content, **kwargs)
        self._session.add(note)
        await self._session.flush()
