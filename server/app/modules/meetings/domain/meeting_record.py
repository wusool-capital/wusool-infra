"""
app/modules/meetings/domain/meeting_record.py

Read models for the `meetings` table (app/models/meeting.py), framework-free
so `application/ports/meetings.py` can depend on them without pulling
SQLAlchemy across the domain/application boundary.

`MeetingRecord` mirrors the full row (the desktop-push flow's dedupe check
and completion/failure bookkeeping need every field). `MeetingSyncStatus` is
the deliberately narrow projection for the sync-status listing — id,
local_recording_id, status, and a computed summary_available flag, never the
transcript/summary bodies.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.utilities.domain.json_types import JsonObject

__all__ = ["MeetingRecord", "MeetingSyncStatus"]


@dataclass(frozen=True, slots=True)
class MeetingRecord:
    id: UUID
    org_id: str | None
    org_name_raw: str | None
    counterparty_role: str | None
    meeting_type: str | None
    occurred_at: datetime
    title: str | None
    source: str
    audio_ref: str | None
    duration_s: int | None
    created_by_ref: str | None
    participants: JsonObject | None
    transcript: str | None
    summary: str | None
    metadata: JsonObject
    created_at: datetime
    scribe_meeting_id: UUID | None
    status: str
    install_id: str | None
    local_recording_id: str | None
    summary_json: JsonObject | None
    summary_started_at: datetime | None


@dataclass(frozen=True, slots=True)
class MeetingSyncStatus:
    id: UUID
    local_recording_id: str | None
    status: str
    summary_available: bool
