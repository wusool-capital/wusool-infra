"""ORM row <-> domain entity translation, one function per concept. This is
where the "domain must not import SQLAlchemy" boundary is actually enforced:
application/domain code consumes the domain dataclasses below, never the
`app.models` ORM classes directly. Mirrors `matching_engine`'s own
`persistence/mappers.py` convention.
"""

from app.models import Meeting, Organization
from app.modules.meetings.domain.meeting_record import MeetingRecord, MeetingStatus
from app.modules.meetings.domain.organization_ref import OrganizationRef

_VALID_STATUSES = frozenset(("summarizing", "completed", "failed"))


def to_meeting_status(value: str) -> MeetingStatus:
    """Narrows the ORM's plain `str` column to `MeetingStatus`. Raising
    here rather than casting blindly: the `ck_meetings_status` CHECK
    constraint should make this unreachable, but a real violation (a
    manual `UPDATE`, a constraint that gets dropped in a future migration)
    should surface as a loud, specific error here — not a `MeetingRecord`
    silently claiming a status the type system says is impossible.
    """
    if value not in _VALID_STATUSES:
        raise ValueError(f"meetings.status has an unexpected value: {value!r}")
    return value  # type: ignore[return-value]  # narrowed by the check above


def to_meeting_record(meeting: Meeting) -> MeetingRecord:
    return MeetingRecord(
        id=meeting.id,
        org_id=meeting.org_id,
        org_name_raw=meeting.org_name_raw,
        counterparty_role=meeting.counterparty_role,
        meeting_type=meeting.meeting_type,
        occurred_at=meeting.occurred_at,
        title=meeting.title,
        source=meeting.source,
        audio_ref=meeting.audio_ref,
        duration_s=meeting.duration_s,
        created_by_ref=meeting.created_by_ref,
        participants=meeting.participants,
        transcript=meeting.transcript,
        summary=meeting.summary,
        metadata=meeting.metadata_,
        created_at=meeting.created_at,
        scribe_meeting_id=meeting.scribe_meeting_id,
        status=to_meeting_status(meeting.status),
        install_id=meeting.install_id,
        local_recording_id=meeting.local_recording_id,
        summary_json=meeting.summary_json,
        summary_started_at=meeting.summary_started_at,
    )


def to_organization_ref(org: Organization) -> OrganizationRef:
    return OrganizationRef(attio_id=org.attio_id, name=org.name)
