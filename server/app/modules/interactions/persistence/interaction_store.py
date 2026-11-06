"""Implements `InteractionStorePort` on the tables from migration `d5f8b2a17c94`."""

from collections.abc import Sequence
from datetime import datetime
from typing import cast

from sqlalchemy import Table, Text, bindparam, delete, func, or_, select, update
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, InteractionParticipant, MailboxSyncCursor
from app.modules.interactions.application.ports.interaction_store import (
    AddressLink,
    NewInteraction,
    PageBatch,
    Source,
    SyncCursor,
)
from app.modules.interactions.domain.model import Channel

_UNIQUE_SOURCE = "uq_interactions_mailbox_source"


class SqlAlchemyInteractionStore:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def read_cursor(self, mailbox: str, source: Source) -> SyncCursor | None:
        async with self._sessionmaker() as session:
            row = await session.get(MailboxSyncCursor, (mailbox, source.value))
        if row is None:
            return None
        return SyncCursor(
            mailbox=row.mailbox,
            source=Source(row.source),
            cursor=row.cursor,
            backfill_page_token=row.backfill_page_token,
            backfill_completed_at=row.backfill_completed_at,
            last_synced_at=row.last_synced_at,
            created_at=row.created_at,
        )

    async def save_page(self, batch: PageBatch) -> int:
        emails = [i for i in batch.items if i.channel is Channel.EMAIL]
        meetings = [i for i in batch.items if i.channel is Channel.MEETING]
        async with self._sessionmaker() as session, session.begin():
            written = await self._insert_emails(session, emails)
            written += await self._upsert_meetings(session, meetings)
            if batch.cancelled_source_ids:
                await session.execute(
                    update(Interaction)
                    .where(
                        Interaction.mailbox == batch.mailbox,
                        Interaction.channel == Channel.MEETING.value,
                        Interaction.source_id.in_(batch.cancelled_source_ids),
                    )
                    .values(cancelled=True, updated_at=func.now())
                )
            if batch.cursor is not None:
                await self._write_cursor(session, batch.cursor)
        return written

    async def unlinked_addresses(self, internal_domains: tuple[str, ...]) -> tuple[str, ...]:
        stmt = (
            select(InteractionParticipant.email)
            .where(
                or_(
                    InteractionParticipant.person_attio_id.is_(None),
                    InteractionParticipant.organization_attio_id.is_(None),
                ),
                InteractionParticipant.domain.not_in(internal_domains),
            )
            .distinct()
            .order_by(InteractionParticipant.email)
        )
        async with self._sessionmaker() as session:
            return tuple((await session.execute(stmt)).scalars())

    async def set_links(self, links: Sequence[AddressLink]) -> int:
        if not links:
            return 0
        # Core, not ORM: the ORM would demand primary keys for a bulk update, and we match by
        # address. coalesce keeps a link that is already set, so a later pass never undoes one.
        # SQLAlchemy types `__table__` as a bare FromClause; a mapped class always has a Table.
        table = cast(Table, InteractionParticipant.__table__)
        stmt = (
            update(table)
            .where(table.c.email == bindparam("b_email"))
            .values(
                person_attio_id=func.coalesce(
                    table.c.person_attio_id, bindparam("b_person", type_=Text)
                ),
                organization_attio_id=func.coalesce(
                    table.c.organization_attio_id, bindparam("b_org", type_=Text)
                ),
            )
        )
        params = [
            {"b_email": x.email, "b_person": x.person_id, "b_org": x.organization_id} for x in links
        ]
        async with self._sessionmaker() as session, session.begin():
            await session.execute(stmt, params)
        return len(links)

    async def purge_before(self, cutoff: datetime) -> int:
        stmt = delete(Interaction).where(Interaction.occurred_at < cutoff).returning(Interaction.id)
        async with self._sessionmaker() as session, session.begin():
            return len((await session.execute(stmt)).all())

    async def _insert_emails(self, session: AsyncSession, items: list[NewInteraction]) -> int:
        """Mail never changes after it arrives, so a re-read row is left as it is."""
        if not items:
            return 0
        stmt = (
            insert(Interaction)
            .values([_row(i) for i in items])
            .on_conflict_do_nothing(constraint=_UNIQUE_SOURCE)
            .returning(Interaction.id, Interaction.source_id)
        )
        ids = {source_id: row_id for row_id, source_id in (await session.execute(stmt)).all()}
        await _add_participants(session, [i for i in items if i.source_id in ids], ids)
        return len(ids)

    async def _upsert_meetings(self, session: AsyncSession, items: list[NewInteraction]) -> int:
        """A moved or renamed meeting keeps its row and replaces its time, title and guests."""
        if not items:
            return 0
        stmt = insert(Interaction).values([_row(i) for i in items])
        stmt = stmt.on_conflict_do_update(
            constraint=_UNIQUE_SOURCE,
            set_={
                "dedupe_key": stmt.excluded.dedupe_key,
                "occurred_at": stmt.excluded.occurred_at,
                "subject": stmt.excluded.subject,
                "cancelled": False,
                "updated_at": func.now(),
            },
        ).returning(Interaction.id, Interaction.source_id)
        ids = {source_id: row_id for row_id, source_id in (await session.execute(stmt)).all()}
        await session.execute(
            delete(InteractionParticipant).where(
                InteractionParticipant.interaction_id.in_(list(ids.values()))
            )
        )
        await _add_participants(session, items, ids)
        return len(ids)

    async def _write_cursor(self, session: AsyncSession, cursor: SyncCursor) -> None:
        stmt = insert(MailboxSyncCursor).values(
            mailbox=cursor.mailbox,
            source=cursor.source.value,
            cursor=cursor.cursor,
            backfill_page_token=cursor.backfill_page_token,
            backfill_completed_at=cursor.backfill_completed_at,
            last_synced_at=cursor.last_synced_at,
        )
        await session.execute(
            stmt.on_conflict_do_update(
                index_elements=[MailboxSyncCursor.mailbox, MailboxSyncCursor.source],
                set_={
                    "cursor": stmt.excluded.cursor,
                    "backfill_page_token": stmt.excluded.backfill_page_token,
                    "backfill_completed_at": stmt.excluded.backfill_completed_at,
                    "last_synced_at": stmt.excluded.last_synced_at,
                    "updated_at": func.now(),
                },
            )
        )


def _row(item: NewInteraction) -> dict[str, str | datetime | None]:
    return {
        "mailbox": item.mailbox,
        "channel": item.channel.value,
        "source_id": item.source_id,
        "dedupe_key": item.dedupe_key,
        "occurred_at": item.occurred_at,
        "direction": item.direction.value if item.direction else None,
        "thread_id": item.thread_id,
        "subject": item.subject,
    }


async def _add_participants(
    session: AsyncSession, items: list[NewInteraction], ids: dict[str, object]
) -> None:
    rows = [
        {
            "interaction_id": ids[item.source_id],
            "email": p.email,
            "domain": p.domain,
            "role": p.role.value,
        }
        for item in items
        for p in item.participants
    ]
    if rows:
        await session.execute(insert(InteractionParticipant), rows)
