"""`SqlAlchemyInteractionStore` against a real Postgres."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, InteractionParticipant, Organization, Person
from app.modules.interactions.application.ports.interaction_store import (
    AddressLink,
    NewInteraction,
    NewParticipant,
    PageBatch,
    Source,
    SyncCursor,
)
from app.modules.interactions.domain.model import Channel, Direction, Role
from app.modules.interactions.persistence.interaction_store import SqlAlchemyInteractionStore

WHEN = datetime(2026, 11, 5, 12, 0, tzinfo=UTC)
SARA = "sara@acme.com"
JULES = "jules@wusoolcapital.com"
INTERNAL = ("wusoolcapital.com", "dopaminecap.com")


def _mail(
    mailbox: str, source_id: str, *, occurred_at: datetime = WHEN, subject: str = "Hi"
) -> NewInteraction:
    return NewInteraction(
        mailbox=mailbox,
        channel=Channel.EMAIL,
        source_id=source_id,
        dedupe_key=f"<{source_id}@mail>",
        occurred_at=occurred_at,
        direction=Direction.INBOUND,
        thread_id=f"t-{source_id}",
        subject=subject,
        participants=(
            NewParticipant(SARA, "acme.com", Role.FROM),
            NewParticipant(JULES, "wusoolcapital.com", Role.TO),
        ),
    )


def _meeting(
    mailbox: str,
    source_id: str,
    *,
    occurred_at: datetime = WHEN,
    subject: str = "Board call",
    guests: tuple[str, ...] = (SARA,),
) -> NewInteraction:
    return NewInteraction(
        mailbox=mailbox,
        channel=Channel.MEETING,
        source_id=source_id,
        dedupe_key=f"{source_id}@google.com|{occurred_at.isoformat()}",
        occurred_at=occurred_at,
        direction=None,
        thread_id=None,
        subject=subject,
        participants=tuple(NewParticipant(g, g.split("@")[1], Role.ATTENDEE) for g in guests),
    )


def _batch(
    mailbox: str,
    *items: NewInteraction,
    source: Source = Source.GMAIL,
    cancelled: tuple[str, ...] = (),
    cursor: SyncCursor | None = None,
) -> PageBatch:
    return PageBatch(mailbox, source, items, cancelled, cursor)


async def _interactions(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> list[Interaction]:
    stmt = select(Interaction).where(Interaction.mailbox == mailbox).order_by(Interaction.source_id)
    async with sessionmaker() as session:
        return list((await session.execute(stmt)).scalars())


async def _participants(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> list[InteractionParticipant]:
    stmt = (
        select(InteractionParticipant)
        .join(Interaction, Interaction.id == InteractionParticipant.interaction_id)
        .where(Interaction.mailbox == mailbox)
        .order_by(InteractionParticipant.email, InteractionParticipant.role)
    )
    async with sessionmaker() as session:
        return list((await session.execute(stmt)).scalars())


async def test_emails_are_saved_with_their_participants(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)

    written = await store.save_page(_batch(mailbox, _mail(mailbox, "m1"), _mail(mailbox, "m2")))

    rows = await _interactions(sessionmaker, mailbox)
    assert written == 2
    assert [(r.source_id, r.channel, r.direction, r.cancelled) for r in rows] == [
        ("m1", "email", "inbound", False),
        ("m2", "email", "inbound", False),
    ]
    assert rows[0].thread_id == "t-m1"
    assert rows[0].subject == "Hi"
    assert len(await _participants(sessionmaker, mailbox)) == 4


async def test_re_reading_an_email_changes_nothing(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(_batch(mailbox, _mail(mailbox, "m1", subject="First")))

    written = await store.save_page(_batch(mailbox, _mail(mailbox, "m1", subject="Edited")))

    rows = await _interactions(sessionmaker, mailbox)
    assert written == 0
    assert [r.subject for r in rows] == ["First"]
    assert len(await _participants(sessionmaker, mailbox)) == 2


async def test_the_same_source_id_in_another_mailbox_is_a_separate_row(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    other = f"other-{mailbox}"
    store = SqlAlchemyInteractionStore(sessionmaker)

    try:
        await store.save_page(_batch(mailbox, _mail(mailbox, "m1")))
        written = await store.save_page(_batch(other, _mail(other, "m1")))
        assert written == 1
    finally:
        async with sessionmaker() as session, session.begin():
            await session.execute(delete(Interaction).where(Interaction.mailbox == other))


async def test_a_moved_meeting_keeps_its_row_and_replaces_time_title_and_guests(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(_batch(mailbox, _meeting(mailbox, "e1"), source=Source.CALENDAR))
    original = (await _interactions(sessionmaker, mailbox))[0]
    moved_to = WHEN + timedelta(days=2)

    written = await store.save_page(
        _batch(
            mailbox,
            _meeting(
                mailbox, "e1", occurred_at=moved_to, subject="Renamed", guests=("bo@acme.com",)
            ),
            source=Source.CALENDAR,
        )
    )

    (row,) = await _interactions(sessionmaker, mailbox)
    assert written == 1
    assert row.id == original.id
    assert (row.occurred_at, row.subject) == (moved_to, "Renamed")
    assert row.dedupe_key.endswith(moved_to.isoformat())
    assert [p.email for p in await _participants(sessionmaker, mailbox)] == ["bo@acme.com"]


async def test_a_cancelled_meeting_is_flagged_and_an_update_brings_it_back(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(_batch(mailbox, _meeting(mailbox, "e1"), source=Source.CALENDAR))

    await store.save_page(_batch(mailbox, source=Source.CALENDAR, cancelled=("e1",)))
    assert [r.cancelled for r in await _interactions(sessionmaker, mailbox)] == [True]

    await store.save_page(_batch(mailbox, _meeting(mailbox, "e1"), source=Source.CALENDAR))
    assert [r.cancelled for r in await _interactions(sessionmaker, mailbox)] == [False]


async def test_cancelling_an_id_never_touches_an_email_with_the_same_id(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(_batch(mailbox, _mail(mailbox, "same")))

    await store.save_page(_batch(mailbox, source=Source.CALENDAR, cancelled=("same",)))

    assert [r.cancelled for r in await _interactions(sessionmaker, mailbox)] == [False]


async def test_a_cursor_round_trips_and_a_batch_without_one_leaves_it_alone(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    assert await store.read_cursor(mailbox, Source.GMAIL) is None
    first = SyncCursor(mailbox, Source.GMAIL, "h100", "p2", None, None)
    await store.save_page(_batch(mailbox, cursor=first))

    saved = await store.read_cursor(mailbox, Source.GMAIL)
    assert saved is not None
    assert (saved.cursor, saved.backfill_page_token, saved.backfill_completed_at) == (
        "h100",
        "p2",
        None,
    )
    assert saved.created_at is not None

    await store.save_page(_batch(mailbox, _mail(mailbox, "m1")))
    assert await store.read_cursor(mailbox, Source.GMAIL) == saved

    done = SyncCursor(mailbox, Source.GMAIL, "h200", None, WHEN, WHEN)
    await store.save_page(_batch(mailbox, cursor=done))
    updated = await store.read_cursor(mailbox, Source.GMAIL)
    assert updated is not None
    assert (updated.cursor, updated.backfill_page_token) == ("h200", None)
    assert (updated.backfill_completed_at, updated.last_synced_at) == (WHEN, WHEN)
    assert updated.created_at == saved.created_at


async def test_gmail_and_calendar_cursors_for_one_mailbox_are_kept_apart(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    await store.save_page(
        _batch(mailbox, cursor=SyncCursor(mailbox, Source.GMAIL, "h1", None, None, None))
    )
    await store.save_page(
        _batch(
            mailbox,
            source=Source.CALENDAR,
            cursor=SyncCursor(mailbox, Source.CALENDAR, "sync-1", None, None, None),
        )
    )

    gmail = await store.read_cursor(mailbox, Source.GMAIL)
    calendar = await store.read_cursor(mailbox, Source.CALENDAR)
    assert gmail is not None
    assert calendar is not None
    assert (gmail.cursor, calendar.cursor) == ("h1", "sync-1")


async def test_unlinked_addresses_skip_the_team_and_anything_fully_linked(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    person_id, org_id = f"{record_prefix}p", f"{record_prefix}o"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=org_id, name="Acme"))
        await session.flush()
        session.add(Person(attio_id=person_id, name="Sara", company_attio_id=org_id))
    await store.save_page(_batch(mailbox, _mail(mailbox, "m1")))

    before = await store.unlinked_addresses(INTERNAL)
    await store.set_links([AddressLink(SARA, person_id, org_id)])
    after = await store.unlinked_addresses(INTERNAL)

    assert SARA in before
    assert JULES not in before
    assert SARA not in after


async def test_a_link_that_is_already_set_is_never_overwritten(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    first, second = f"{record_prefix}p1", f"{record_prefix}p2"
    org_id = f"{record_prefix}o"
    async with sessionmaker() as session, session.begin():
        session.add(Organization(attio_id=org_id, name="Acme"))
        await session.flush()
        session.add_all([Person(attio_id=first, name="A"), Person(attio_id=second, name="B")])
    await store.save_page(_batch(mailbox, _mail(mailbox, "m1")))

    await store.set_links([AddressLink(SARA, first, None)])
    await store.set_links([AddressLink(SARA, second, org_id)])

    sara = next(p for p in await _participants(sessionmaker, mailbox) if p.email == SARA)
    # The person stayed as first set; the organization, still empty, was filled in.
    assert (sara.person_attio_id, sara.organization_attio_id) == (first, org_id)


async def test_setting_no_links_is_a_no_op(
    sessionmaker: async_sessionmaker[AsyncSession],
) -> None:
    assert await SqlAlchemyInteractionStore(sessionmaker).set_links([]) == 0


async def test_purging_removes_old_interactions_and_their_participants_only(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str
) -> None:
    store = SqlAlchemyInteractionStore(sessionmaker)
    # Dates far in the past, so the purge cannot touch any real interaction in this database.
    old = datetime(2001, 1, 1, tzinfo=UTC)
    recent = datetime(2003, 1, 1, tzinfo=UTC)
    later = datetime(2004, 1, 1, tzinfo=UTC)
    await store.save_page(
        _batch(
            mailbox,
            _mail(mailbox, "old", occurred_at=old),
            _mail(mailbox, "recent", occurred_at=recent),
            _meeting(mailbox, "later", occurred_at=later),
        )
    )

    removed = await store.purge_before(datetime(2002, 1, 1, tzinfo=UTC))

    assert removed == 1
    assert [r.source_id for r in await _interactions(sessionmaker, mailbox)] == ["later", "recent"]
    assert len(await _participants(sessionmaker, mailbox)) == 3
