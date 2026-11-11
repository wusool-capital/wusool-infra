"""Implements `TouchReaderPort` from the interaction tables."""

import uuid
from collections import defaultdict
from collections.abc import Mapping

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.models import Interaction, InteractionParticipant
from app.modules.interactions.domain.model import Channel, Direction, Role, Touch
from app.modules.interactions.domain.touch_building import (
    StoredItem,
    StoredParticipant,
    touches_by_organization,
)


class SqlAlchemyTouchReader:
    def __init__(
        self, sessionmaker: async_sessionmaker[AsyncSession], internal_domains: tuple[str, ...]
    ) -> None:
        self._sessionmaker = sessionmaker
        self._internal_domains = internal_domains

    async def touches_by_organization(self) -> Mapping[str, tuple[Touch, ...]]:
        linked = (
            select(InteractionParticipant.interaction_id)
            .where(InteractionParticipant.organization_attio_id.is_not(None))
            .distinct()
        )
        stmt = (
            select(
                Interaction.id,
                Interaction.mailbox,
                Interaction.dedupe_key,
                Interaction.channel,
                Interaction.direction,
                Interaction.occurred_at,
                Interaction.subject,
                InteractionParticipant.email,
                InteractionParticipant.role,
                InteractionParticipant.organization_attio_id,
            )
            .join(InteractionParticipant, InteractionParticipant.interaction_id == Interaction.id)
            .where(Interaction.cancelled.is_(False), Interaction.id.in_(linked))
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(stmt)).all()

        participants: dict[uuid.UUID, list[StoredParticipant]] = defaultdict(list)
        heads: dict[uuid.UUID, StoredItem] = {}
        for row in rows:
            participants[row.id].append(
                StoredParticipant(row.email, Role(row.role), row.organization_attio_id)
            )
            heads.setdefault(
                row.id,
                StoredItem(
                    mailbox=row.mailbox,
                    dedupe_key=row.dedupe_key,
                    channel=Channel(row.channel),
                    direction=Direction(row.direction) if row.direction else None,
                    occurred_at=row.occurred_at,
                    subject=row.subject,
                    participants=(),
                ),
            )
        items = [
            StoredItem(
                head.mailbox,
                head.dedupe_key,
                head.channel,
                head.direction,
                head.occurred_at,
                head.subject,
                tuple(participants[item_id]),
            )
            for item_id, head in heads.items()
        ]
        return touches_by_organization(items, self._internal_domains)
