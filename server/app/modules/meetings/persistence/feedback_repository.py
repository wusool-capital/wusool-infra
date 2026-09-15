"""Read/write access to the `feedback_submissions` table for
`POST /desktop/feedback`. `add()`/`flush()`/`execute()` only — never
`commit()`/`rollback()`; the caller (the `get_session` dependency) owns the
transaction boundary, matching `MeetingsRepository`'s own contract.
"""

from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import FeedbackSubmission


class FeedbackRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(
        self,
        *,
        id: UUID,
        category: str,
        message: str,
        contact: str | None,
        install_id: str,
        app_version: str,
        platform: str,
    ) -> None:
        self._session.add(
            FeedbackSubmission(
                id=id,
                category=category,
                message=message,
                contact=contact,
                install_id=install_id,
                app_version=app_version,
                platform=platform,
            )
        )
        await self._session.flush()

    async def mark_email_sent(self, *, id: UUID) -> None:
        """A separate UPDATE, not a mutation on the `create()`-time ORM
        instance -- keeps the ORM object from leaking back out of this
        repository (see this module's docstring)."""
        await self._session.execute(
            update(FeedbackSubmission)
            .where(FeedbackSubmission.id == id)
            .values(email_sent=True, email_sent_at=datetime.now(UTC))
        )
