"""Pydantic DTOs at the desktop API's boundary — data definitions and
domain -> DTO converters only, matching the desktop app's Rust client's
existing wire contract field-for-field (`wusool-scribe`'s
`app.desktop.schemas`), except: no artifact/queue-specific fields (this
module acks-then-BackgroundTasks, not SQS), and `summary` is a typed
`DesktopSummarySchema` instead of Scribe's `dict[str, Any]` — same JSON
shape on the wire, stricter type on our side.

`client_version`/`slack_channel_id` are accepted so a Scribe-era desktop
push still validates, then dropped: this module has no Slack delivery and
doesn't otherwise use them.
"""

from __future__ import annotations

import uuid
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.modules.meetings.domain.meeting_record import MeetingRecord, MeetingSyncStatus
from app.modules.meetings.domain.organization_ref import OrganizationRef
from app.modules.meetings.domain.summary import MeetingSummary, SummaryNote


class DesktopTranscriptTurn(BaseModel):
    speaker: str
    start: float
    end: float
    text: str


class DesktopMeetingSubmitRequest(BaseModel):
    """Payload the desktop app pushes once the user finishes editing and
    tagging a locally recorded/transcribed meeting."""

    install_id: str = Field(..., min_length=1, max_length=64)
    local_recording_id: str = Field(..., min_length=1)
    transcript: list[DesktopTranscriptTurn]
    duration_seconds: float = Field(..., ge=0)
    # The meeting's actual start time, computed client-side from the local
    # recording (not the push time) -- a meeting can be pushed long after
    # it happened, so the server should never derive this from its own
    # now() when it doesn't have to. Optional (not every desktop install
    # updates the moment the server does): a client still on the previous
    # release that omits this field falls back to the old approximation
    # in IngestMixin.ingest_meeting rather than getting a 422.
    occurred_at: datetime | None = None
    buyer_query: str | None = None
    buyer_selection: str | None = None
    seller_query: str | None = None
    seller_selection: str | None = None
    investor_query: str | None = None
    investor_selection: str | None = None
    internal_query: str | None = None
    internal_selection: str | None = None
    general_query: str | None = None
    general_selection: str | None = None
    org_names: dict[str, str] = Field(default_factory=dict)
    # Accepted-and-dropped: no Slack delivery, no version-gating in this module.
    slack_channel_id: str | None = None
    client_version: str | None = None
    return_summary: bool = True


class DesktopMeetingSubmitResponse(BaseModel):
    meeting_id: uuid.UUID
    status: str
    already_existed: bool


class DesktopVerifyResponse(BaseModel):
    """Backs the desktop app's Save-time config check — reaching this
    route at all already proves the server URL and API key are both
    correct, since `require_desktop_api_key` runs first."""

    status: str = "ok"


class SummaryNoteSchema(BaseModel):
    topic: str
    points: list[str] = Field(default_factory=list)


class DesktopSummarySchema(BaseModel):
    """Same 9 fields, same JSON shape as Scribe's summary dict — typed
    here instead, per this module's one approved deviation from Scribe's
    wire contract."""

    title: str
    executive_summary: str
    notes: list[SummaryNoteSchema] = Field(default_factory=list)
    decisions: list[str] = Field(default_factory=list)
    action_items: list[str] = Field(default_factory=list)
    claims_to_verify: list[str] = Field(default_factory=list)
    risks: list[str] = Field(default_factory=list)
    deal_momentum: str = ""
    keywords: list[str] = Field(default_factory=list)


class DesktopMeetingStatusResponse(BaseModel):
    """Backs the desktop app's poll for the finished summary."""

    meeting_id: uuid.UUID
    status: str
    summary: DesktopSummarySchema | None = None


class DesktopMeetingSyncItem(BaseModel):
    meeting_id: uuid.UUID
    local_recording_id: str
    status: str
    summary_available: bool


class DesktopMeetingSyncResponse(BaseModel):
    meetings: list[DesktopMeetingSyncItem]


class DesktopCompanyCandidate(BaseModel):
    label: str
    value: str


class DesktopCompanySearchResponse(BaseModel):
    candidates: list[DesktopCompanyCandidate]
    org_names: dict[str, str]


class FeedbackCategory(StrEnum):
    """Kept in sync BY HAND with two other copies -- there is no shared
    codegen across these three languages. Changing a member here means
    also updating `CATEGORIES` in
    `scribe-desktop/frontend/src-tauri/src/feedback/mod.rs` and
    `FEEDBACK_CATEGORIES` in `scribe-desktop/frontend/src/lib/feedback.ts`.
    """

    BUG = "bug"
    FEATURE_REQUEST = "feature_request"
    TRANSCRIPTION_QUALITY = "transcription_quality"
    OTHER = "other"


class DesktopFeedbackRequest(BaseModel):
    """In-app feedback from the desktop app. Durably recorded in
    `feedback_submissions` (see `api/feedback.py`) before anything else
    happens -- that row is the source of truth. A best-effort SES email
    notification is scheduled afterward and never gates the response, so
    the request always returns 200 once the row is written.
    """

    model_config = ConfigDict(str_strip_whitespace=True)

    # message/contact's max_length are kept in sync BY HAND with
    # MAX_MESSAGE_CHARS/MAX_CONTACT_CHARS (feedback/mod.rs) and
    # MAX_FEEDBACK_CHARS (lib/feedback.ts).
    message: str = Field(..., min_length=1, max_length=4000)
    category: FeedbackCategory
    # "email or name" -- free text by design, so no EmailStr (and
    # email-validator isn't a dependency of this project).
    contact: str | None = Field(default=None, max_length=200)
    install_id: str = Field(..., min_length=1, max_length=64)
    app_version: str = Field(..., min_length=1, max_length=32)
    platform: str = Field(..., min_length=1, max_length=120)


class DesktopFeedbackResponse(BaseModel):
    status: str = "ok"


def to_summary_note_schema(note: SummaryNote) -> SummaryNoteSchema:
    return SummaryNoteSchema(topic=note.topic, points=note.points)


def to_summary_schema(summary: MeetingSummary) -> DesktopSummarySchema:
    return DesktopSummarySchema(
        title=summary.title,
        executive_summary=summary.executive_summary,
        notes=[to_summary_note_schema(note) for note in summary.notes],
        decisions=summary.decisions,
        action_items=summary.action_items,
        claims_to_verify=summary.claims_to_verify,
        risks=summary.risks,
        deal_momentum=summary.deal_momentum,
        keywords=summary.keywords,
    )


def to_status_response(meeting: MeetingRecord) -> DesktopMeetingStatusResponse:
    summary = (
        DesktopSummarySchema.model_validate(meeting.summary_json)
        if meeting.summary_json is not None
        else None
    )
    return DesktopMeetingStatusResponse(
        meeting_id=meeting.id, status=meeting.status, summary=summary
    )


def to_sync_item(status: MeetingSyncStatus) -> DesktopMeetingSyncItem:
    return DesktopMeetingSyncItem(
        meeting_id=status.id,
        local_recording_id=status.local_recording_id or "",
        status=status.status,
        summary_available=status.summary_available,
    )


def to_company_candidate(org: OrganizationRef) -> DesktopCompanyCandidate:
    return DesktopCompanyCandidate(label=org.name, value=f"attio:{org.attio_id}")


class TranscriptSegmentSchema(BaseModel):
    segment_id: str = Field(..., min_length=1)
    text: str


# Roughly 3.5 hours of speech; each 12k chars costs one Bedrock call.
_MAX_CORRECTION_SEGMENTS = 5000
_MAX_CORRECTION_TOTAL_CHARS = 200_000


class TranscriptCorrectionsRequest(BaseModel):
    segments: list[TranscriptSegmentSchema] = Field(..., max_length=_MAX_CORRECTION_SEGMENTS)

    @field_validator("segments")
    @classmethod
    def _bounded_and_unique(
        cls, segments: list[TranscriptSegmentSchema]
    ) -> list[TranscriptSegmentSchema]:
        if len({s.segment_id for s in segments}) != len(segments):
            raise ValueError("segment_id values must be unique")
        if sum(len(s.text) for s in segments) > _MAX_CORRECTION_TOTAL_CHARS:
            raise ValueError(f"transcript exceeds {_MAX_CORRECTION_TOTAL_CHARS} characters")
        return segments


class CorrectionSuggestionSchema(BaseModel):
    segment_id: str
    original: str
    suggested: str
    reason: str


class TranscriptCorrectionsResponse(BaseModel):
    suggestions: list[CorrectionSuggestionSchema]
