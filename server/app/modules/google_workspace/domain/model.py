"""Framework-free shapes of what Gmail and Calendar return."""

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class MailMessage:
    """One Gmail message as fetched: headers and labels only, never a body."""

    source_id: str
    thread_id: str
    # The Message-ID header is the same in every mailbox that received the mail.
    message_id: str | None
    occurred_at: datetime
    labels: frozenset[str]
    subject: str | None
    from_address: str | None
    to_addresses: tuple[str, ...]
    cc_addresses: tuple[str, ...]
    auto_submitted: str | None
    has_list_unsubscribe: bool


@dataclass(frozen=True)
class Attendee:
    address: str
    response_status: str | None
    is_self: bool


@dataclass(frozen=True)
class CalendarEvent:
    """One calendar event occurrence. A cancelled one may arrive with only its id."""

    source_id: str
    cancelled: bool
    ical_uid: str | None
    starts_at: datetime | None
    all_day: bool
    subject: str | None
    organizer: str | None
    attendees: tuple[Attendee, ...]
