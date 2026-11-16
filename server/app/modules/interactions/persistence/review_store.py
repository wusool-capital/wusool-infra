"""Implements `ReviewStorePort` on `interaction_review_items`."""

from collections.abc import Sequence

from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, InteractionParticipant, InteractionReviewItem
from app.modules.interactions.application.ports.review import OpenReview, ReviewCase
from app.modules.interactions.domain.linking import Ambiguity

_OPEN = "open"


class SqlAlchemyReviewStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def save_open(self, cases: Sequence[ReviewCase]) -> None:
        if not cases:
            return
        async with self._sessionmaker() as session, session.begin():
            for case in cases:
                stmt = (
                    insert(InteractionReviewItem)
                    .values(
                        kind=case.kind.value,
                        value=case.value,
                        subject=_latest_subject(case),
                        record_attio_ids=list(case.record_ids),
                    )
                    .on_conflict_do_nothing(
                        index_elements=["kind", "value"], index_where=text("status = 'open'")
                    )
                )
                await session.execute(stmt)

    async def list_open(self) -> tuple[OpenReview, ...]:
        stmt = (
            select(
                InteractionReviewItem.kind,
                InteractionReviewItem.value,
                InteractionReviewItem.subject,
                InteractionReviewItem.record_attio_ids,
            )
            .where(InteractionReviewItem.status == _OPEN)
            .order_by(InteractionReviewItem.created_at, InteractionReviewItem.value)
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(stmt)).all()
        return tuple(
            OpenReview(Ambiguity(kind), value, subject, len(ids))
            for kind, value, subject, ids in rows
        )


def _latest_subject(case: ReviewCase):  # noqa: ANN202 - a scalar subquery has no public type
    column = (
        InteractionParticipant.email
        if case.kind is Ambiguity.SHARED_EMAIL
        else InteractionParticipant.domain
    )
    return (
        select(Interaction.subject)
        .join(InteractionParticipant, InteractionParticipant.interaction_id == Interaction.id)
        .where(column == case.value, Interaction.subject.is_not(None))
        .order_by(Interaction.occurred_at.desc())
        .limit(1)
        .scalar_subquery()
    )
