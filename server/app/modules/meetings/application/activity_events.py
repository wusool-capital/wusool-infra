"""Builds the `activities` events a meeting's publish and delete record."""

from app.modules.activities import (
    ActivityActor,
    ActivityEvent,
    ActivitySource,
    EventType,
    MeetingPayload,
    SubjectType,
)
from app.modules.meetings.domain.meeting_record import MeetingRecord


def meeting_event(
    event_type: EventType, meeting: MeetingRecord, *, pushed_to_attio: bool = False
) -> ActivityEvent:
    """Anchored on the organization when the meeting has one, else on the
    meeting itself, so an internal meeting still lands on the timeline."""
    if meeting.org_id is not None:
        subject_type, subject_attio_id = SubjectType.ORGANIZATION, meeting.org_id
    else:
        subject_type, subject_attio_id = SubjectType.MEETING, None
    return ActivityEvent(
        subject_type=subject_type,
        event_type=event_type,
        source=ActivitySource.MEETINGS,
        actor=ActivityActor.scribe(meeting.install_id),
        payload=MeetingPayload(pushed_to_attio=pushed_to_attio),
        subject_attio_id=subject_attio_id,
        subject_uuid=meeting.id,
        meeting_id=meeting.id,
        idempotency_key=f"{event_type}:{meeting.id}",
    )
