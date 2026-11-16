"""Review items: one open item per value, resolved when fixed, dismissed ones stay dismissed."""

from datetime import UTC, datetime

from sqlalchemy import delete, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import InteractionReviewItem
from app.modules.interactions.application.ports.interaction_store import (
    NewInteraction,
    NewParticipant,
    PageBatch,
    Source,
)
from app.modules.interactions.application.ports.review import ReviewCase
from app.modules.interactions.domain.linking import Ambiguity
from app.modules.interactions.domain.model import Channel, Direction, Role
from app.modules.interactions.persistence.interaction_store import SqlAlchemyInteractionStore
from app.modules.interactions.persistence.review_store import SqlAlchemyReviewStore

WHEN = datetime(2026, 11, 5, 12, tzinfo=UTC)


async def _mail(store: SqlAlchemyInteractionStore, mailbox: str, sender: str, subject: str) -> None:
    domain = sender.split("@")[1]
    await store.save_page(
        PageBatch(
            mailbox,
            Source.GMAIL,
            (
                NewInteraction(
                    mailbox=mailbox,
                    channel=Channel.EMAIL,
                    source_id="m1",
                    dedupe_key="m1-key",
                    occurred_at=WHEN,
                    direction=Direction.INBOUND,
                    thread_id="t1",
                    subject=subject,
                    participants=(NewParticipant(sender, domain, Role.FROM),),
                ),
            ),
            (),
            None,
        )
    )


async def _forget(sessionmaker: async_sessionmaker[AsyncSession], value: str) -> None:
    async with sessionmaker() as session, session.begin():
        await session.execute(
            delete(InteractionReviewItem).where(InteractionReviewItem.value == value)
        )


async def test_a_case_is_saved_once_with_its_latest_subject(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    shared = f"{record_prefix}info@acme.com"
    await _mail(SqlAlchemyInteractionStore(sessionmaker), mailbox, shared, "Term sheet")
    reviews = SqlAlchemyReviewStore(sessionmaker)
    case = ReviewCase(Ambiguity.SHARED_EMAIL, shared, (f"{record_prefix}p1", f"{record_prefix}p2"))
    try:
        await reviews.sync_open([case])
        await reviews.sync_open([case])

        found = [r for r in await reviews.list_open() if r.value == shared]

        assert [(r.kind, r.subject, r.record_count, r.notified) for r in found] == [
            (Ambiguity.SHARED_EMAIL, "Term sheet", 2, False)
        ]
    finally:
        await _forget(sessionmaker, shared)


async def test_a_shared_domain_finds_its_subject_through_a_subdomain_address(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    parent = f"{record_prefix}shared.example"
    await _mail(
        SqlAlchemyInteractionStore(sessionmaker), mailbox, f"a@mail.{parent}", "Subdomain mail"
    )
    reviews = SqlAlchemyReviewStore(sessionmaker)
    try:
        await reviews.sync_open([ReviewCase(Ambiguity.SHARED_DOMAIN, parent, ("o1", "o2"))])

        (found,) = [r for r in await reviews.list_open() if r.value == parent]

        assert found.subject == "Subdomain mail"
    finally:
        await _forget(sessionmaker, parent)


async def test_a_case_that_is_no_longer_found_resolves_and_notified_cases_are_marked(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    kept = ReviewCase(Ambiguity.SHARED_EMAIL, f"{record_prefix}keep@acme.com", ("p1", "p2"))
    fixed = ReviewCase(Ambiguity.SHARED_EMAIL, f"{record_prefix}fixed@acme.com", ("p3", "p4"))
    reviews = SqlAlchemyReviewStore(sessionmaker)
    try:
        await reviews.sync_open([kept, fixed])
        listed = [r for r in await reviews.list_open() if r.value.startswith(record_prefix)]
        await reviews.mark_notified(listed)

        await reviews.sync_open([kept])

        left = [r for r in await reviews.list_open() if r.value.startswith(record_prefix)]
        assert [(r.value, r.notified) for r in left] == [(kept.value, True)]
    finally:
        await _forget(sessionmaker, kept.value)
        await _forget(sessionmaker, fixed.value)


async def test_a_dismissed_case_does_not_come_back(
    sessionmaker: async_sessionmaker[AsyncSession], record_prefix: str
) -> None:
    case = ReviewCase(Ambiguity.SHARED_EMAIL, f"{record_prefix}info@acme.com", ("p1", "p2"))
    reviews = SqlAlchemyReviewStore(sessionmaker)
    try:
        await reviews.sync_open([case])
        async with sessionmaker() as session, session.begin():
            await session.execute(
                update(InteractionReviewItem)
                .where(InteractionReviewItem.value == case.value)
                .values(status="dismissed")
            )

        await reviews.sync_open([case])

        assert [r for r in await reviews.list_open() if r.value == case.value] == []
    finally:
        await _forget(sessionmaker, case.value)
