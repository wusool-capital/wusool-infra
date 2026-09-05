"""Shared constructor for every application-layer mixin in this module —
each mixin subclasses this instead of redeclaring its own `__init__`, so
`service.py`'s composed facade ends up with exactly one constructor no
matter how many mixins it combines. Mirrors `matching_engine`'s
`application/base.py`.

`summarization_service` is a collaborator object, not a mixin — it stays
its own standalone class since nothing outside `PublishMixin` calls it
directly (see `summarize.py`'s own docstring).

This module's `tests/test_architecture.py` forbids `domain/`/`application/`
from importing `app.modules.meetings.providers` (or `.persistence`, `.api`),
so `ServiceBase` never constructs `AttioNoteWriter`/`BedrockConverseClient`
itself — it only ever receives already-constructed Port implementations /
collaborator objects, injected by `bootstrap.py` (a later phase). The note
writer is typed against `NoteWriterPort` (a Protocol `AttioNoteWriter`
satisfies structurally) rather than importing the concrete class, for the
same reason.
"""

import asyncio

from app.modules.meetings.application.ports.meetings import MeetingsRepositoryPort
from app.modules.meetings.application.ports.note_writer import NoteWriterPort
from app.modules.meetings.application.ports.notes import NotesRepositoryPort
from app.modules.meetings.application.ports.organizations import OrganizationLookupPort
from app.modules.meetings.application.summarize import SummarizationService


class ServiceBase:
    def __init__(
        self,
        *,
        meetings_repository: MeetingsRepositoryPort,
        notes_repository: NotesRepositoryPort,
        organization_lookup: OrganizationLookupPort,
        summarization_service: SummarizationService,
        note_writer: NoteWriterPort | None,
        attio_note_object_slug: str | None,
        max_concurrent_summaries: int,
    ) -> None:
        self._meetings_repository = meetings_repository
        self._notes_repository = notes_repository
        self._organization_lookup = organization_lookup
        self._summarization_service = summarization_service
        self._note_writer = note_writer
        self._attio_note_object_slug = attio_note_object_slug
        self._max_concurrent_summaries = max_concurrent_summaries
        # Constructed once and reused across calls — gates only the
        # expensive LLM call in `PublishMixin.summarize_and_publish`, never
        # the row-creation/dedup path in `IngestMixin`.
        self._summary_semaphore = asyncio.Semaphore(max_concurrent_summaries)
