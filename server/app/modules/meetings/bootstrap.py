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

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.meetings.application.service import MeetingsService
from app.modules.meetings.application.summarize import SummarizationService
from app.modules.meetings.config import get_settings
from app.modules.meetings.persistence.meetings_repository import MeetingsRepository
from app.modules.meetings.persistence.notes_repository import NotesRepository
from app.modules.meetings.persistence.organization_lookup import OrganizationLookup
from app.modules.meetings.providers.attio.note_writer import AttioNoteWriter
from app.modules.meetings.providers.bedrock.client import BedrockConverseClient


def build_meetings_repository(session: AsyncSession) -> MeetingsRepository:
    return MeetingsRepository(session)


def build_notes_repository(session: AsyncSession) -> NotesRepository:
    return NotesRepository(session)


def build_organization_lookup(session: AsyncSession) -> OrganizationLookup:
    return OrganizationLookup(session)


def build_bedrock_client() -> BedrockConverseClient:
    return BedrockConverseClient()


def build_note_writer() -> AttioNoteWriter:
    return AttioNoteWriter()


def build_summarization_service() -> SummarizationService:
    settings = get_settings()
    return SummarizationService(
        build_bedrock_client(),
        model_id=settings.aws_bedrock_model_id,
        summary_max_tokens=settings.summary_max_tokens,
        summary_max_tokens_per_chunk=settings.summary_max_tokens_per_chunk,
    )


def build_meetings_service(session: AsyncSession) -> MeetingsService:
    """`session` backs `meetings_repository`/`notes_repository`/
    `organization_lookup` — every method call the returned service makes
    must happen before that session closes.
    """
    settings = get_settings()
    return MeetingsService(
        meetings_repository=build_meetings_repository(session),
        notes_repository=build_notes_repository(session),
        organization_lookup=build_organization_lookup(session),
        summarization_service=build_summarization_service(),
        note_writer=build_note_writer(),
        attio_note_object_slug=settings.attio_note_object_slug,
        max_concurrent_summaries=settings.max_concurrent_summaries,
    )
