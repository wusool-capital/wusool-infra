"""`PublishMixin.summarize_and_publish` / `_write_note` — pure-fake unit
tests, no DB. Every transcript used here is under `SummarizationService`'s
20-word floor, so `summarize()` returns its fixed "no content" summary
without ever calling the LLM port — the fake `SummarizerLLM` below is never
invoked; it only needs to exist to satisfy `SummarizationService`'s
constructor.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from uuid import UUID, uuid4

import pytest

from app.modules.meetings.application.service import MeetingsService
from app.modules.meetings.application.summarize import SummarizationService
from app.modules.meetings.domain.meeting_record import MeetingRecord
from app.modules.meetings.domain.role_ref import ActiveRoleRef
from app.modules.meetings.domain.roles import MeetingRole
from app.modules.utilities.domain.json_types import JsonObject

_MEETING_ID = uuid4()
_ORG_ID = "org-attio-1"

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
    status="summarizing",
    install_id="install-1",
    local_recording_id="rec-1",
    summary_json=None,
    summary_started_at=None,
    note_id=None,
)


def _meeting(**overrides: object) -> MeetingRecord:
    return replace(_DEFAULT_MEETING, **overrides)  # type: ignore[arg-type]


class _FakeSummarizerLLM:
    async def summarize(
        self, *, model_id: str, prompt: str, system_prompt: str, max_tokens: int, temperature: float
    ) -> JsonObject:
        raise AssertionError("LLM should never be called for a short transcript in these tests")


def _summarization_service() -> SummarizationService:
    return SummarizationService(
        _FakeSummarizerLLM(),
        model_id="fake-model",
        summary_max_tokens=100,
        summary_max_tokens_per_chunk=100,
    )


@dataclass
class _FakeMeetingsRepository:
    meeting: MeetingRecord
    mark_completed_calls: list[dict[str, object]] = field(default_factory=list)
    mark_failed_calls: list[dict[str, object]] = field(default_factory=list)
    set_note_id_calls: list[dict[str, object]] = field(default_factory=list)
    fail_set_note_id: bool = False

    async def get_by_install_and_recording(self, install_id, local_recording_id):
        raise NotImplementedError

    async def create(self, **kwargs):
        raise NotImplementedError

    async def mark_completed(self, meeting_id, *, summary_text, summary_json, title):
        self.mark_completed_calls.append(
            {"meeting_id": meeting_id, "summary_text": summary_text, "title": title}
        )

    async def mark_failed(self, meeting_id, *, reason):
        self.mark_failed_calls.append({"meeting_id": meeting_id, "reason": reason})

    async def set_note_id(self, meeting_id, *, note_id):
        if self.fail_set_note_id:
            raise RuntimeError("writeback failed")
        self.set_note_id_calls.append({"meeting_id": meeting_id, "note_id": note_id})

    async def recover_stalled(self, meeting_id, *, cutoff):
        raise NotImplementedError

    async def get_by_id(self, meeting_id):
        return self.meeting

    async def list_by_install_id(self, install_id, *, limit):
        raise NotImplementedError


@dataclass
class _FakeNotesRepository:
    calls: list[dict[str, object]] = field(default_factory=list)
    fail: bool = False
    returned_id: UUID = field(default_factory=uuid4)

    async def create(
        self,
        *,
        note_id,
        organization_id,
        note_type,
        content,
        primary_role,
        buyer_role_id,
        seller_role_id,
    ) -> UUID:
        if self.fail:
            raise RuntimeError("insert failed")
        self.calls.append(
            {
                "note_id": note_id,
                "organization_id": organization_id,
                "note_type": note_type,
                "primary_role": primary_role,
                "buyer_role_id": buyer_role_id,
                "seller_role_id": seller_role_id,
            }
        )
        return note_id or self.returned_id


@dataclass
class _FakeNoteWriter:
    calls: list[dict[str, object]] = field(default_factory=list)
    returned_id: UUID | None = None

    async def push_note(
        self,
        *,
        organization_attio_id,
        content,
        created_at,
        primary_role,
        buyer_role_entry_id,
        seller_role_entry_id,
    ) -> UUID | None:
        self.calls.append(
            {
                "organization_attio_id": organization_attio_id,
                "primary_role": primary_role,
                "buyer_role_entry_id": buyer_role_entry_id,
                "seller_role_entry_id": seller_role_entry_id,
            }
        )
        return self.returned_id


@dataclass
class _FakeRoleLookup:
    buyer_role: ActiveRoleRef | None = None
    seller_role: ActiveRoleRef | None = None
    buyer_calls: list[str] = field(default_factory=list)
    seller_calls: list[str] = field(default_factory=list)

    async def get_active_buyer_role(self, org_attio_id: str) -> ActiveRoleRef | None:
        self.buyer_calls.append(org_attio_id)
        return self.buyer_role

    async def get_active_seller_role(self, org_attio_id: str) -> ActiveRoleRef | None:
        self.seller_calls.append(org_attio_id)
        return self.seller_role


@dataclass
class _FakeOrganizationLookup:
    async def get_by_id(self, attio_id: str):
        raise NotImplementedError

    async def search_by_name(self, term: str, limit: int):
        raise NotImplementedError


def _service(
    *,
    meeting: MeetingRecord,
    notes_repo: _FakeNotesRepository | None = None,
    note_writer: _FakeNoteWriter | None = None,
    role_lookup: _FakeRoleLookup | None = None,
) -> tuple[
    MeetingsService, _FakeMeetingsRepository, _FakeNotesRepository, _FakeNoteWriter, _FakeRoleLookup
]:
    meetings_repo = _FakeMeetingsRepository(meeting=meeting)
    notes_repo = notes_repo or _FakeNotesRepository()
    note_writer = note_writer or _FakeNoteWriter()
    role_lookup = role_lookup or _FakeRoleLookup()
    service = MeetingsService(
        meetings_repository=meetings_repo,
        notes_repository=notes_repo,
        organization_lookup=_FakeOrganizationLookup(),
        role_lookup=role_lookup,
        summarization_service=_summarization_service(),
        note_writer=note_writer,
        summary_semaphore=asyncio.Semaphore(1),
    )
    return service, meetings_repo, notes_repo, note_writer, role_lookup


async def test_org_less_meeting_still_gets_a_note() -> None:
    """Regression test for the removed `publish.py:78-83` early return: a
    meeting with no resolved org must still file a note, on both sides."""
    meeting = _meeting(org_id=None, primary_role=None)
    service, meetings_repo, notes_repo, note_writer, role_lookup = _service(meeting=meeting)

    await service.summarize_and_publish(_MEETING_ID)

    assert len(meetings_repo.mark_completed_calls) == 1
    assert len(notes_repo.calls) == 1
    call = notes_repo.calls[0]
    assert call["organization_id"] is None
    assert call["buyer_role_id"] is None
    assert call["seller_role_id"] is None
    assert note_writer.calls[0]["organization_attio_id"] is None
    assert role_lookup.buyer_calls == []
    assert role_lookup.seller_calls == []
    assert meetings_repo.set_note_id_calls  # write-back happened


async def test_buyer_primary_attaches_buyer_role_only() -> None:
    role = ActiveRoleRef(id=uuid4(), legacy_entry_id="entry-buyer-1")
    meeting = _meeting(org_id=_ORG_ID, primary_role=MeetingRole.BUYER)
    service, _, notes_repo, note_writer, role_lookup = _service(
        meeting=meeting, role_lookup=_FakeRoleLookup(buyer_role=role)
    )

    await service.summarize_and_publish(_MEETING_ID)

    assert role_lookup.buyer_calls == [_ORG_ID]
    assert role_lookup.seller_calls == []
    call = notes_repo.calls[0]
    assert call["buyer_role_id"] == role.id
    assert call["seller_role_id"] is None
    attio_call = note_writer.calls[0]
    assert attio_call["buyer_role_entry_id"] == "entry-buyer-1"
    assert attio_call["seller_role_entry_id"] is None


async def test_seller_primary_attaches_seller_role_only() -> None:
    role = ActiveRoleRef(id=uuid4(), legacy_entry_id="entry-seller-1")
    meeting = _meeting(org_id=_ORG_ID, primary_role=MeetingRole.SELLER)
    service, _, notes_repo, note_writer, role_lookup = _service(
        meeting=meeting, role_lookup=_FakeRoleLookup(seller_role=role)
    )

    await service.summarize_and_publish(_MEETING_ID)

    assert role_lookup.seller_calls == [_ORG_ID]
    assert role_lookup.buyer_calls == []
    call = notes_repo.calls[0]
    assert call["seller_role_id"] == role.id
    assert call["buyer_role_id"] is None
    attio_call = note_writer.calls[0]
    assert attio_call["seller_role_entry_id"] == "entry-seller-1"
    assert attio_call["buyer_role_entry_id"] is None


@pytest.mark.parametrize("role", [MeetingRole.INVESTOR, MeetingRole.INTERNAL, MeetingRole.GENERAL])
async def test_non_buyer_seller_primary_never_looks_up_a_role(role: MeetingRole) -> None:
    meeting = _meeting(org_id=_ORG_ID, primary_role=role)
    service, _, notes_repo, _, role_lookup = _service(meeting=meeting)

    await service.summarize_and_publish(_MEETING_ID)

    assert role_lookup.buyer_calls == []
    assert role_lookup.seller_calls == []
    call = notes_repo.calls[0]
    assert call["buyer_role_id"] is None
    assert call["seller_role_id"] is None
    assert call["primary_role"] == role.value


async def test_org_present_but_no_active_role_row_still_writes_the_note() -> None:
    meeting = _meeting(org_id=_ORG_ID, primary_role=MeetingRole.BUYER)
    service, _, notes_repo, _, role_lookup = _service(
        meeting=meeting, role_lookup=_FakeRoleLookup(buyer_role=None)
    )

    await service.summarize_and_publish(_MEETING_ID)

    assert role_lookup.buyer_calls == [_ORG_ID]
    call = notes_repo.calls[0]
    assert call["buyer_role_id"] is None
    assert call["organization_id"] == _ORG_ID


async def test_role_with_no_legacy_entry_id_sets_postgres_uuid_but_omits_attio_key() -> None:
    """Clobber-hazard mitigation: when the role row has no `legacy_entry_id`,
    the link is skipped on BOTH sides (not just Attio) so a later inbound
    `note.updated`/`note.created` webhook can't resolve the omitted Attio
    field back to NULL and overwrite a uuid Postgres alone would have set."""
    role = ActiveRoleRef(id=uuid4(), legacy_entry_id=None)
    meeting = _meeting(org_id=_ORG_ID, primary_role=MeetingRole.BUYER)
    service, _, notes_repo, note_writer, _ = _service(
        meeting=meeting, role_lookup=_FakeRoleLookup(buyer_role=role)
    )

    await service.summarize_and_publish(_MEETING_ID)

    call = notes_repo.calls[0]
    assert call["buyer_role_id"] is None
    attio_call = note_writer.calls[0]
    assert attio_call["buyer_role_entry_id"] is None


async def test_note_id_written_back_to_the_meeting_on_success() -> None:
    meeting = _meeting(org_id=_ORG_ID, primary_role=None)
    fixed_id = uuid4()
    service, meetings_repo, _, _, _ = _service(
        meeting=meeting, notes_repo=_FakeNotesRepository(returned_id=fixed_id)
    )

    await service.summarize_and_publish(_MEETING_ID)

    assert meetings_repo.set_note_id_calls == [{"meeting_id": _MEETING_ID, "note_id": fixed_id}]


async def test_note_id_not_written_back_when_notes_insert_fails() -> None:
    meeting = _meeting(org_id=_ORG_ID, primary_role=None)
    service, meetings_repo, _, _, _ = _service(
        meeting=meeting, notes_repo=_FakeNotesRepository(fail=True)
    )

    await service.summarize_and_publish(_MEETING_ID)

    # Meeting still completed even though the note failed.
    assert meetings_repo.mark_completed_calls
    assert meetings_repo.set_note_id_calls == []


async def test_writeback_failure_does_not_raise() -> None:
    meeting = _meeting(org_id=_ORG_ID, primary_role=None)
    meetings_repo = _FakeMeetingsRepository(meeting=meeting, fail_set_note_id=True)
    notes_repo = _FakeNotesRepository()
    service = MeetingsService(
        meetings_repository=meetings_repo,
        notes_repository=notes_repo,
        organization_lookup=_FakeOrganizationLookup(),
        role_lookup=_FakeRoleLookup(),
        summarization_service=_summarization_service(),
        note_writer=_FakeNoteWriter(),
        summary_semaphore=asyncio.Semaphore(1),
    )

    await service.summarize_and_publish(_MEETING_ID)  # must not raise

    assert meetings_repo.set_note_id_calls == []


async def test_primary_role_reaches_meeting_note_and_attio() -> None:
    meeting = _meeting(org_id=None, primary_role=MeetingRole.INTERNAL)
    service, _, notes_repo, note_writer, _ = _service(meeting=meeting)

    await service.summarize_and_publish(_MEETING_ID)

    assert notes_repo.calls[0]["primary_role"] == "internal"
    assert note_writer.calls[0]["primary_role"] == "internal"
