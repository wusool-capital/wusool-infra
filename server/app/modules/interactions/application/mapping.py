"""Turning fetched Gmail messages and Calendar events into rows to store.

Pure: no I/O. Anything the ignore filter drops returns None.
"""

from datetime import UTC

from app.modules.google_workspace import CalendarEvent, MailMessage
from app.modules.interactions.application.ports.interaction_store import (
    NewInteraction,
    NewParticipant,
)
from app.modules.interactions.domain.addresses import domain_of, is_internal, team_member_of
from app.modules.interactions.domain.filters import is_ignored
from app.modules.interactions.domain.model import Channel, Direction, RawItem, Role


def email_to_item(
    mailbox: str, message: MailMessage, internal_domains: tuple[str, ...]
) -> NewInteraction | None:
    roles = [
        (Role.FROM, [message.from_address] if message.from_address else []),
        (Role.TO, list(message.to_addresses)),
        (Role.CC, list(message.cc_addresses)),
    ]
    participants = _participants(roles, internal_domains)
    raw = RawItem(
        channel=Channel.EMAIL,
        participants=tuple(dict.fromkeys(p.email for p in participants)),
        labels=message.labels,
        subject=message.subject,
        auto_submitted=message.auto_submitted,
    )
    if is_ignored(raw, internal_domains):
        return None
    sent_by_us = message.from_address is not None and is_internal(
        message.from_address, internal_domains
    )
    return NewInteraction(
        mailbox=mailbox,
        channel=Channel.EMAIL,
        source_id=message.source_id,
        # Without a Message-ID the copy in each mailbox can't be matched, so each counts alone.
        dedupe_key=message.message_id or f"gmail:{message.source_id}",
        occurred_at=message.occurred_at,
        direction=Direction.OUTBOUND if sent_by_us else Direction.INBOUND,
        thread_id=message.thread_id,
        subject=message.subject,
        participants=participants,
    )


def event_to_item(
    mailbox: str, event: CalendarEvent, internal_domains: tuple[str, ...]
) -> NewInteraction | None:
    if event.starts_at is None or event.ical_uid is None:
        return None
    # An attendee who declined never took part, so their address is not recorded.
    attending = [a.address for a in event.attendees if a.response_status != "declined"]
    listed = {a.address for a in event.attendees}
    # An organizer missing from the guest list took part; one who is listed and declined did not.
    if event.organizer and event.organizer not in listed:
        attending.append(event.organizer)
    participants = _participants([(Role.ATTENDEE, attending)], internal_domains)
    raw = RawItem(
        channel=Channel.MEETING,
        participants=tuple(p.email for p in participants),
        subject=event.subject,
        all_day=event.all_day,
        team_declined=any(a.is_self and a.response_status == "declined" for a in event.attendees),
    )
    if is_ignored(raw, internal_domains):
        return None
    return NewInteraction(
        mailbox=mailbox,
        channel=Channel.MEETING,
        source_id=event.source_id,
        dedupe_key=f"{event.ical_uid}|{event.starts_at.astimezone(UTC).isoformat()}",
        occurred_at=event.starts_at,
        direction=None,
        thread_id=None,
        subject=event.subject,
        participants=participants,
    )


def _participants(
    roles: list[tuple[Role, list[str]]], internal_domains: tuple[str, ...]
) -> tuple[NewParticipant, ...]:
    """One row per address and role. Team aliases fold into one address first."""
    unique: dict[tuple[str, Role], NewParticipant] = {}
    for role, addresses in roles:
        for address in addresses:
            email = team_member_of(address, internal_domains)
            unique.setdefault((email, role), NewParticipant(email, domain_of(email), role))
    return tuple(unique.values())
