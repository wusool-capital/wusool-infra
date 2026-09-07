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
        self,
        *,
        note_id: UUID | None,
        organization_id: str | None,
        note_type: str,
        content: str,
        primary_role: str | None,
        buyer_role_id: UUID | None,
        seller_role_id: UUID | None,
    ) -> UUID:
        """`note_id` is supplied when the row must reuse Attio's own record id
        (the note was already pushed to Attio); left `None` lets the column's
        own `gen_random_uuid()` server default apply (Postgres-only case, no
        Attio push).

        The insert runs inside its own savepoint: `PublishMixin.
        summarize_and_publish` has already run `mark_completed` for this
        meeting earlier in the same outer transaction by the time this runs,
        and this call's own `flush()` can fail (a bad enum-checked value, an FK
        violation). Without the savepoint, a failed flush leaves the whole
        `AsyncSession` in pending-rollback, so the outer `session.commit()`
        would raise and silently discard that already-succeeded
        `mark_completed`, stranding the meeting in `summarizing` forever. A
        savepoint rollback keeps the outer transaction usable instead.
        """
        note = Note(
            organization_id=organization_id,
            note_type=note_type,
            content=content,
            primary_role=primary_role,
            buyer_role_id=buyer_role_id,
            seller_role_id=seller_role_id,
            **({"id": note_id} if note_id is not None else {}),
        )
        async with self._session.begin_nested():
            self._session.add(note)
            await self._session.flush()
        return note.id
