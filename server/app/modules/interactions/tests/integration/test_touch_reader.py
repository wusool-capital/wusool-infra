"""Stored rows read back as touches: cancelled meetings are left out and links decide the org."""

from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Organization, Person
from app.modules.interactions.application.ports.interaction_store import (
    AddressLink,
    NewInteraction,
    NewParticipant,
    PageBatch,
    Source,
)
from app.modules.interactions.domain.model import Channel, Direction, Role
from app.modules.interactions.persistence.interaction_store import SqlAlchemyInteractionStore
from app.modules.interactions.persistence.touch_reader import SqlAlchemyTouchReader

WHEN = datetime(2026, 11, 5, 12, tzinfo=UTC)
INTERNAL = ("wusoolcapital.com", "dopaminecap.com")


def _item(mailbox: str, contact: str, channel: Channel, source_id: str) -> NewInteraction:
    role = Role.FROM if channel is Channel.EMAIL else Role.ATTENDEE
    return NewInteraction(
        mailbox=mailbox,
        channel=channel,
        source_id=source_id,
        dedupe_key=f"{source_id}-key",
        occurred_at=WHEN,
        direction=Direction.INBOUND if channel is Channel.EMAIL else None,
        thread_id=None,
        subject="Hi",
        participants=(
            NewParticipant(contact, "acme.com", role),
            NewParticipant(mailbox, "wusoolcapital.com", Role.TO),
        ),
    )


async def test_linked_touches_are_read_and_cancelled_meetings_are_not(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    org_id = f"{record_prefix}o"
    # A unique address, so linking it can never touch rows from another test.
    contact = f"{record_prefix}sara@acme.com"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=org_id, name="Acme"))
        await session.flush()
        session.add(Person(attio_id=f"{record_prefix}p", name="Sara", company_attio_id=org_id))
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(
        PageBatch(mailbox, Source.GMAIL, (_item(mailbox, contact, Channel.EMAIL, "m1"),), (), None)
    )
    await store.save_page(
        PageBatch(
            mailbox,
            Source.CALENDAR,
            (
                _item(mailbox, contact, Channel.MEETING, "e1"),
                _item(mailbox, contact, Channel.MEETING, "e2"),
            ),
            ("e2",),
            None,
        )
    )
    await store.set_links([AddressLink(contact, f"{record_prefix}p", org_id)])

    by_org = await SqlAlchemyTouchReader(sessionmaker, INTERNAL).touches_by_organization()

    touches = by_org[org_id]
    assert sorted((t.channel.value, t.dedupe_key) for t in touches) == [
        ("email", "m1-key"),
        ("meeting", "e1-key"),
    ]
    assert {t.team_member for t in touches} == {mailbox}

    by_person = await SqlAlchemyTouchReader(sessionmaker, INTERNAL).touches_by_person()
    assert sorted(t.dedupe_key for t in by_person[f"{record_prefix}p"]) == ["e1-key", "m1-key"]
