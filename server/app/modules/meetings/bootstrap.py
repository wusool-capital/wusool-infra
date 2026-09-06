"""Composition root for this module: holds the `build_*` factory functions
`api/dependencies.py` consumes instead of constructing concrete persistence/
provider classes inline. Sits at the module root, outside `domain/`/
`application/`, so — unlike those two layers — it is free to import
`persistence/`/`providers/` concrete classes here; it still never imports
`fastapi`/`pydantic` since nothing here needs them.

NOT the deployed entrypoint — `server/main.py` wires the real router in (a
later phase), the same way `matching_engine`'s `bootstrap.py` factories are
consumed by its `api/dependencies.py` rather than by its own `create_app()`.
"""

import asyncio
import logging
from functools import lru_cache
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.application.ports.note_writer import NoteWriterPort
from app.modules.meetings.application.service import MeetingsService
from app.modules.meetings.application.summarize import SummarizationService
from app.modules.meetings.config import get_settings
from app.modules.meetings.persistence.database import get_sessionmaker
from app.modules.meetings.persistence.meetings_repository import MeetingsRepository
from app.modules.meetings.persistence.notes_repository import NotesRepository
from app.modules.meetings.persistence.organization_lookup import OrganizationLookup
from app.modules.meetings.providers.attio.note_writer import AttioNoteWriter
from app.modules.meetings.providers.bedrock.client import BedrockConverseClient

logger = logging.getLogger(__name__)


def build_meetings_repository(session: AsyncSession) -> MeetingsRepository:
    return MeetingsRepository(session)


def build_notes_repository(session: AsyncSession) -> NotesRepository:
    return NotesRepository(session)


def build_organization_lookup(session: AsyncSession) -> OrganizationLookup:
    return OrganizationLookup(session)


def build_bedrock_client() -> BedrockConverseClient:
    return BedrockConverseClient()


def build_note_writer() -> NoteWriterPort | None:
    """`None` when `ATTIO_NOTE_OBJECT_SLUG` is unset — matching this
    module's documented "Attio push is optional" behavior. Constructing
    `AttioNoteWriter()` eagerly calls `app.modules.attio.get_attio_client()`,
    which requires `ATTIO_API_KEY` at construction time; a deployment that
    only sets this module's own env vars (no Attio workspace configured at
    all) must not fail every request just because a writer nothing will
    ever call got built anyway.
    """
    if not get_settings().attio_note_object_slug:
        return None
    return AttioNoteWriter()


def build_summarization_service() -> SummarizationService:
    settings = get_settings()
    return SummarizationService(
        build_bedrock_client(),
        model_id=settings.aws_bedrock_model_id,
        summary_max_tokens=settings.summary_max_tokens,
        summary_max_tokens_per_chunk=settings.summary_max_tokens_per_chunk,
    )


@lru_cache
def _summary_semaphore() -> asyncio.Semaphore:
    """Process-wide, built once — see `ServiceBase`'s docstring for why
    this cannot be built per-`MeetingsService` (one is constructed fresh
    per request)."""
    return asyncio.Semaphore(get_settings().max_concurrent_summaries)


def build_meetings_service(session: AsyncSession) -> MeetingsService:
    """`session` backs `meetings_repository`/`notes_repository`/
    `organization_lookup` — every method call the returned service makes
    must happen before that session closes. Do not hand a service built
    this way to `BackgroundTasks` — use `run_summarize_and_publish` for
    background work instead, which owns its own session.
    """
    settings = get_settings()
    return MeetingsService(
        meetings_repository=build_meetings_repository(session),
        notes_repository=build_notes_repository(session),
        organization_lookup=build_organization_lookup(session),
        summarization_service=build_summarization_service(),
        note_writer=build_note_writer(),
        attio_note_object_slug=settings.attio_note_object_slug,
        summary_semaphore=_summary_semaphore(),
    )


async def run_summarize_and_publish(meeting_id: UUID) -> None:
    """The `BackgroundTasks` entrypoint for summarization — opens and owns
    its own session/service, independent of whatever request-scoped
    session triggered it.

    Never share a request's `MeetingsService` (built by
    `build_meetings_service`) with a background task: that session is
    committed and closed as soon as the triggering request's dependency
    generator resumes, which happens once the response is on its way —
    not guaranteed to be after a scheduled background task has run. Using
    an already-closed/rolled-back session from a background task would
    silently drop this call's writes (`mark_completed`/`mark_failed`), or
    raise on first use if the underlying connection was already returned
    to the pool.

    `PublishMixin.summarize_and_publish` never raises (it converts a
    failure into `mark_failed` itself), so the only thing this wrapper
    adds is committing that write — logged, not re-raised, since this
    runs detached from any request with no one to hand an exception to.
    """
    async with get_sessionmaker()() as session:
        service = build_meetings_service(session)
        try:
            await service.summarize_and_publish(meeting_id)
            await session.commit()
        except Exception:
            await session.rollback()
            logger.error("run_summarize_and_publish_failed", extra={"meeting_id": str(meeting_id)})
