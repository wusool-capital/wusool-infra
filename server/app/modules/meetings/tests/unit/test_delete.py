"""`DeleteMixin.delete_meeting` — pure-fake unit tests, no DB. Mirrors
`test_publish.py`'s fake style.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.modules.meetings.application.errors import MeetingStillProcessingError
from app.modules.meetings.application.service import MeetingsService
from app.modules.meetings.application.summarize import SummarizationService
from app.modules.meetings.domain.meeting_record import MeetingRecord
from app.modules.utilities.domain.json_types import JsonObject

_MEETING_ID = uuid4()
_NOTE_ID = uuid4()
_INSTALL_ID = "install-1"
_LOCAL_RECORDING_ID = "rec-1"

_DEFAULT_MEETING = MeetingRecord(
    id=_MEETING_ID,
    org_id=None,
    org_name_raw=None,
    counterparty_role=None,
    meeting_type=None,
    primary_role=None,
    occurred_at=datetime(2026, 9, 7, tzinfo=UTC),
    title=None,
    source="in_house",
    audio_ref=None,
    duration_s=60,
    created_by_ref=None,
    participants=None,
    transcript="short",
    summary=None,
    metadata={},
    created_at=datetime(2026, 9, 7, tzinfo=UTC),
    scribe_meeting_id=None,
    status="completed",
    install_id=_INSTALL_ID,
    local_recording_id=_LOCAL_RECORDING_ID,
    summary_json=None,
    summary_started_at=None,
    note_id=None,
    removed_at=None,
)


def _meeting(**overrides: object) -> MeetingRecord:
    return replace(_DEFAULT_MEETING, **overrides)  # type: ignore[arg-type]


class _FakeSummarizerLLM:
    async def summarize(
        self, *, model_id: str, prompt: str, system_prompt: str, max_tokens: int, temperature: float
    ) -> JsonObject:
        raise AssertionError("delete flow never summarizes")


def _summarization_service() -> SummarizationService:
    return SummarizationService(
        _FakeSummarizerLLM(),
        model_id="fake-model",
        summary_max_tokens=100,
        summary_max_tokens_per_chunk=100,
    )


@dataclass
class _FakeMeetingsRepository:
    meeting: MeetingRecord | None
    mark_failed_calls: list[dict[str, object]] = field(default_factory=list)
    soft_delete_calls: list[UUID] = field(default_factory=list)
    soft_delete_result: bool = True

    async def get_by_install_and_recording(self, install_id, local_recording_id):
        return self.meeting

    async def create(self, **kwargs):
        raise NotImplementedError

    async def mark_completed(self, meeting_id, *, summary_text, summary_json, title):
        raise NotImplementedError

    async def mark_failed(self, meeting_id, *, reason):
        self.mark_failed_calls.append({"meeting_id": meeting_id, "reason": reason})

    async def set_note_id(self, meeting_id, *, note_id):
        raise NotImplementedError

    async def recover_stalled(self, meeting_id, *, cutoff):
        raise NotImplementedError

    async def get_by_id(self, meeting_id):
        raise NotImplementedError

    async def soft_delete(self, meeting_id):
        self.soft_delete_calls.append(meeting_id)
        return self.soft_delete_result

    async def list_by_install_id(self, install_id, *, limit):
        raise NotImplementedError


@dataclass
class _FakeNotesRepository:
    soft_delete_calls: list[UUID] = field(default_factory=list)

    async def create(self, **kwargs) -> UUID:
        raise NotImplementedError

    async def soft_delete(self, note_id):
        self.soft_delete_calls.append(note_id)


@dataclass
class _FakeNoteWriter:
    delete_calls: list[UUID] = field(default_factory=list)
    fail: Exception | None = None

    async def push_note(self, **kwargs):
        raise NotImplementedError

    async def delete_note(self, record_id):
        self.delete_calls.append(record_id)
        if self.fail is not None:
            raise self.fail


@dataclass
class _FakeOrganizationLookup:
    async def get_by_id(self, attio_id: str):
        raise NotImplementedError

    async def search_by_name(self, term: str, limit: int):
        raise NotImplementedError


@dataclass
class _FakeRoleLookup:
    async def get_active_buyer_role(self, org_attio_id: str):
        raise NotImplementedError

    async def get_active_seller_role(self, org_attio_id: str):
        raise NotImplementedError


def _service(
    *,
    meeting: MeetingRecord | None,
    notes_repo: _FakeNotesRepository | None = None,
    note_writer: _FakeNoteWriter | None = None,
) -> tuple[MeetingsService, _FakeMeetingsRepository, _FakeNotesRepository, _FakeNoteWriter]:
    meetings_repo = _FakeMeetingsRepository(meeting=meeting)
    notes_repo = notes_repo or _FakeNotesRepository()
    note_writer = note_writer or _FakeNoteWriter()
    service = MeetingsService(
        meetings_repository=meetings_repo,
        notes_repository=notes_repo,
        organization_lookup=_FakeOrganizationLookup(),
        role_lookup=_FakeRoleLookup(),
        summarization_service=_summarization_service(),
        note_writer=note_writer,
        summary_semaphore=asyncio.Semaphore(1),
    )
    return service, meetings_repo, notes_repo, note_writer


async def test_missing_meeting_is_a_no_op() -> None:
    service, meetings_repo, _, _ = _service(meeting=None)

    await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)  # must not raise

    assert meetings_repo.soft_delete_calls == []


async def test_already_removed_meeting_is_a_no_op() -> None:
    meeting = _meeting(removed_at=datetime(2026, 9, 8, tzinfo=UTC))
    service, meetings_repo, _, _ = _service(meeting=meeting)

    await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)

    assert meetings_repo.soft_delete_calls == []


async def test_actively_summarizing_meeting_raises_409() -> None:
    meeting = _meeting(status="summarizing", summary_started_at=datetime.now(UTC))
    service, meetings_repo, _, _ = _service(meeting=meeting)

    with pytest.raises(MeetingStillProcessingError):
        await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)

    assert meetings_repo.soft_delete_calls == []


async def test_stalled_meeting_is_marked_failed_then_deleted() -> None:
    stale = datetime.now(UTC) - timedelta(minutes=30)
    meeting = _meeting(status="summarizing", summary_started_at=stale)
    service, meetings_repo, _, _ = _service(meeting=meeting)

    await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)

    assert meetings_repo.mark_failed_calls == [
        {"meeting_id": _MEETING_ID, "reason": "deleted from desktop while stalled"}
    ]
    assert meetings_repo.soft_delete_calls == [_MEETING_ID]


async def test_note_deleted_from_attio_before_postgres() -> None:
    meeting = _meeting(note_id=_NOTE_ID)
    note_writer = _FakeNoteWriter()
    notes_repo = _FakeNotesRepository()
    service, meetings_repo, notes_repo, note_writer = _service(
        meeting=meeting, notes_repo=notes_repo, note_writer=note_writer
    )

    await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)

    assert note_writer.delete_calls == [_NOTE_ID]
    assert notes_repo.soft_delete_calls == [_NOTE_ID]
    assert meetings_repo.soft_delete_calls == [_MEETING_ID]


async def test_attio_failure_stops_before_any_postgres_write() -> None:
    meeting = _meeting(note_id=_NOTE_ID)
    note_writer = _FakeNoteWriter(fail=RuntimeError("attio is down"))
    service, meetings_repo, notes_repo, note_writer = _service(
        meeting=meeting, note_writer=note_writer
    )

    with pytest.raises(RuntimeError):
        await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)

    assert notes_repo.soft_delete_calls == []
    assert meetings_repo.soft_delete_calls == []


async def test_meeting_with_no_note_skips_attio_entirely() -> None:
    meeting = _meeting(note_id=None)
    service, meetings_repo, notes_repo, note_writer = _service(meeting=meeting)

    await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)

    assert note_writer.delete_calls == []
    assert notes_repo.soft_delete_calls == []
    assert meetings_repo.soft_delete_calls == [_MEETING_ID]


async def test_soft_delete_returning_false_raises_409() -> None:
    """The row changed under us (re-summarizing / concurrent delete): never
    claim success for a delete that didn't happen."""
    meeting = _meeting(note_id=None)
    service, meetings_repo, _, _ = _service(meeting=meeting)
    meetings_repo.soft_delete_result = False

    with pytest.raises(MeetingStillProcessingError):
        await service.delete_meeting(_INSTALL_ID, _LOCAL_RECORDING_ID)
