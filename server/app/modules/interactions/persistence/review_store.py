"""Implements `ReviewStorePort` on `interaction_review_items`."""

from collections.abc import Sequence

from sqlalchemy import ScalarSelect, func, or_, select, text, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, InteractionParticipant, InteractionReviewItem
from app.modules.interactions.application.ports.review import OpenReview, ReviewCase
from app.modules.interactions.domain.linking import Ambiguity

_OPEN = "open"
_RESOLVED = "resolved"
_DISMISSED = "dismissed"

_Item = InteractionReviewItem


class SqlAlchemyReviewStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def sync_open(self, cases: Sequence[ReviewCase]) -> None:
        current = {(case.kind.value, case.value) for case in cases}
        async with self._sessionmaker() as session, session.begin():
            dismissed_rows = await session.execute(
                select(_Item.kind, _Item.value).where(_Item.status == _DISMISSED)
            )
            dismissed = {(kind, value) for kind, value in dismissed_rows.all()}
            for case in cases:
                if (case.kind.value, case.value) in dismissed:
                    continue
                stmt = (
                    insert(_Item)
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
            open_rows = await session.execute(
                select(_Item.id, _Item.kind, _Item.value).where(_Item.status == _OPEN)
            )
            gone = [id_ for id_, kind, value in open_rows.all() if (kind, value) not in current]
            if gone:
                await session.execute(
                    update(_Item)
                    .where(_Item.id.in_(gone))
                    .values(status=_RESOLVED, updated_at=func.now())
                )

    async def list_open(self) -> tuple[OpenReview, ...]:
        stmt = (
            select(
                _Item.kind,
                _Item.value,
                _Item.subject,
                _Item.record_attio_ids,
                _Item.notified_at.is_not(None),
            )
            .where(_Item.status == _OPEN)
            .order_by(_Item.created_at, _Item.value)
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(stmt)).all()
        return tuple(
            OpenReview(Ambiguity(kind), value, subject, len(ids), notified)
            for kind, value, subject, ids, notified in rows
        )

    async def mark_notified(self, items: Sequence[OpenReview]) -> None:
        if not items:
            return
        async with self._sessionmaker() as session, session.begin():
            for item in items:
                await session.execute(
                    update(_Item)
                    .where(_Item.kind == item.kind.value, _Item.value == item.value)
                    .where(_Item.status == _OPEN)
                    .values(notified_at=func.now())
                )


def _latest_subject(case: ReviewCase) -> ScalarSelect[str | None]:
    if case.kind is Ambiguity.SHARED_EMAIL:
        match = InteractionParticipant.email == case.value
    else:
        # The shared domain may be a parent of the address's own, as in acme.com for mail.acme.com.
        match = or_(
            InteractionParticipant.domain == case.value,
            InteractionParticipant.domain.endswith(f".{case.value}", autoescape=True),
        )
    return (
        select(Interaction.subject)
        .join(InteractionParticipant, InteractionParticipant.interaction_id == Interaction.id)
        .where(match, Interaction.subject.is_not(None))
        .order_by(Interaction.occurred_at.desc())
        .limit(1)
        .scalar_subquery()
    )
