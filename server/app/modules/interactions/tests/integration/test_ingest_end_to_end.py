"""A whole ingest pass through the real store and directory on Postgres. Only Google is faked,
so this checks the pieces fit: mapping, storage, resuming and linking to CRM records."""

from dataclasses import replace

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, InteractionParticipant, Organization, Person
from app.modules.google_workspace import Attendee, CalendarPage, MailPage
from app.modules.interactions.application.ingest import IngestService
from app.modules.interactions.application.ports.interaction_store import Source
from app.modules.interactions.persistence.directory import SqlAlchemyRecordDirectory
from app.modules.interactions.persistence.interaction_store import SqlAlchemyInteractionStore
from app.modules.interactions.tests.fakes.ingest import (
    CONFIG,
    FakeCalendar,
    FakeMail,
    event,
    message,
)
from app.modules.interactions.tests.fakes.touches import NOW


async def test_a_pass_stores_links_and_then_polls_without_repeating_itself(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    org_id, person_id = f"{record_prefix}o", f"{record_prefix}p"
    domain = f"{record_prefix}acme.example"
    sara = f"sara@{domain}"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=org_id, name="Acme", domains=[domain]))
        await session.flush()
        # Stored in capitals, as Attio may hold it; the directory normalises.
        session.add(
            Person(attio_id=person_id, name="Sara", email=[sara.upper()], company_attio_id=org_id)
        )

    mail, calendar = FakeMail(), FakeCalendar()
    mail.backfill_pages = [MailPage((message("m1", sender=sara, to=(mailbox,)),), None)]
    calendar.backfill_pages = [
        CalendarPage(
            (
                event(
                    "e1",
                    attendees=(
                        Attendee(mailbox, "accepted", True),
                        Attendee(sara, "accepted", False),
                    ),
                    organizer=sara,
                ),
            ),
            None,
            "sync-1",
        )
    ]
    store = SqlAlchemyInteractionStore(sessionmaker)
    service = IngestService(
        store,
        SqlAlchemyRecordDirectory(sessionmaker),
        mail,
        calendar,
        replace(CONFIG, mailboxes=(mailbox,)),
        clock=lambda: NOW,
    )

    first = await service.run_pass()

    assert (first.written, first.failures) == (2, ())
    assert first.linked >= 1
    async with sessionmaker() as session:
        rows = (
            (await session.execute(select(Interaction).where(Interaction.mailbox == mailbox)))
            .scalars()
            .all()
        )
        linked = (
            (
                await session.execute(
                    select(InteractionParticipant)
                    .join(Interaction, Interaction.id == InteractionParticipant.interaction_id)
                    .where(Interaction.mailbox == mailbox, InteractionParticipant.email == sara)
                )
            )
            .scalars()
            .all()
        )
    assert sorted(r.channel for r in rows) == ["email", "meeting"]
    assert len(linked) == 2
    assert {(p.person_attio_id, p.organization_attio_id) for p in linked} == {(person_id, org_id)}
    gmail = await store.read_cursor(mailbox, Source.GMAIL)
    calendar_cursor = await store.read_cursor(mailbox, Source.CALENDAR)
    assert gmail is not None
    assert calendar_cursor is not None
    assert (gmail.cursor, gmail.backfill_completed_at) == ("h100", NOW)
    assert (calendar_cursor.cursor, calendar_cursor.backfill_completed_at) == ("sync-1", NOW)

    mail.change_pages = [MailPage((), None, "h101")]
    calendar.change_pages = [CalendarPage((), None, "sync-2")]
    second = await service.run_pass()

    assert second.written == 0
    after = await store.read_cursor(mailbox, Source.GMAIL)
    assert after is not None
    assert after.cursor == "h101"
