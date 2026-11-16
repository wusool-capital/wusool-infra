"""Who the engine may create: a two-way thread or an attended meeting, and no Person yet."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Person
from app.modules.interactions.application.ports.interaction_store import (
    AddressLink,
    NewInteraction,
    NewParticipant,
    PageBatch,
    Source,
)
from app.modules.interactions.domain.model import Channel, Direction, Role
from app.modules.interactions.persistence.candidates import SqlAlchemyCandidateSource
from app.modules.interactions.persistence.interaction_store import SqlAlchemyInteractionStore

WHEN = datetime(2026, 11, 5, 12, tzinfo=UTC)
INTERNAL = ("wusoolcapital.com", "dopaminecap.com")


def _email(
    mailbox: str,
    source_id: str,
    thread: str,
    direction: Direction,
    sender: str,
    recipient: str,
    sender_name: str | None = None,
) -> NewInteraction:
    return NewInteraction(
        mailbox=mailbox,
        channel=Channel.EMAIL,
        source_id=source_id,
        dedupe_key=f"{source_id}-key",
        occurred_at=WHEN,
        direction=direction,
        thread_id=thread,
        subject="Hi",
        participants=(
            NewParticipant(sender, sender.split("@")[1], Role.FROM, sender_name),
            NewParticipant(recipient, recipient.split("@")[1], Role.TO),
        ),
    )


def _meeting(mailbox: str, source_id: str, guest: str) -> NewInteraction:
    return NewInteraction(
        mailbox=mailbox,
        channel=Channel.MEETING,
        source_id=source_id,
        dedupe_key=f"{source_id}-key",
        occurred_at=WHEN,
        direction=None,
        thread_id=None,
        subject="Call",
        participants=(
            NewParticipant(guest, guest.split("@")[1], Role.ATTENDEE),
            NewParticipant(mailbox, "wusoolcapital.com", Role.ATTENDEE),
        ),
    )


async def test_only_unlinked_outsiders_with_a_two_way_thread_or_a_meeting_are_candidates(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    two_way = f"{record_prefix}two@acme.com"
    one_way = f"{record_prefix}one@acme.com"
    attended = f"{record_prefix}met@acme.com"
    cancelled = f"{record_prefix}gone@acme.com"
    linked = f"{record_prefix}known@acme.com"
    thread = f"{record_prefix}t1"
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(
        PageBatch(
            mailbox,
            Source.GMAIL,
            (
                _email(mailbox, "m1", thread, Direction.OUTBOUND, mailbox, two_way),
                _email(mailbox, "m2", thread, Direction.INBOUND, two_way, mailbox, "Sara Lee"),
                _email(mailbox, "m3", f"{thread}b", Direction.INBOUND, one_way, mailbox),
                _email(mailbox, "m4", f"{thread}c", Direction.OUTBOUND, mailbox, linked),
                _email(mailbox, "m5", f"{thread}c", Direction.INBOUND, linked, mailbox),
            ),
            (),
            None,
        )
    )
    await store.save_page(
        PageBatch(
            mailbox,
            Source.CALENDAR,
            (_meeting(mailbox, "e1", attended), _meeting(mailbox, "e2", cancelled)),
            ("e2",),
            None,
        )
    )
    async with sessionmaker() as session, session.begin():
        session.add(Person(attio_id=f"{record_prefix}p", name="Known"))
    await store.set_links([AddressLink(linked, f"{record_prefix}p", None)])

    found = {
        c.email: c
        for c in await SqlAlchemyCandidateSource(sessionmaker).candidates(INTERNAL)
        if c.email.startswith(record_prefix)
    }

    assert set(found) == {two_way, attended}
    assert (found[two_way].two_way_thread, found[two_way].attended_meeting) == (True, False)
    assert (found[attended].two_way_thread, found[attended].attended_meeting) == (False, True)
    assert found[two_way].name == "Sara Lee"
    assert found[attended].name is None
