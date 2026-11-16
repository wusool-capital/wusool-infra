"""Review items: one open item per value, with the latest subject for context."""

from datetime import UTC, datetime

from sqlalchemy import delete
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


async def test_a_case_is_saved_once_with_its_latest_subject(
    sessionmaker: async_sessionmaker[AsyncSession], mailbox: str, record_prefix: str
) -> None:
    shared = f"{record_prefix}info@acme.com"
    store = SqlAlchemyInteractionStore(sessionmaker)
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
                    subject="Term sheet",
                    participants=(NewParticipant(shared, "acme.com", Role.FROM),),
                ),
            ),
            (),
            None,
        )
    )
    reviews = SqlAlchemyReviewStore(sessionmaker)
    case = ReviewCase(Ambiguity.SHARED_EMAIL, shared, (f"{record_prefix}p1", f"{record_prefix}p2"))
    try:
        await reviews.save_open([case])
        await reviews.save_open([case])

        found = [r for r in await reviews.list_open() if r.value == shared]

        assert [(r.kind, r.subject, r.record_count) for r in found] == [
            (Ambiguity.SHARED_EMAIL, "Term sheet", 2)
        ]
    finally:
        async with sessionmaker() as session, session.begin():
            await session.execute(
                delete(InteractionReviewItem).where(InteractionReviewItem.value == shared)
            )
