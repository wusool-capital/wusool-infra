"""Implements `CandidateSourcePort` from the interaction tables."""

from sqlalchemy import Select, and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import aliased

from app.models import Interaction, InteractionParticipant
from app.modules.interactions.application.ports.auto_create import Candidate
from app.modules.interactions.domain.model import Channel, Direction, Role


class SqlAlchemyCandidateSource:
    def __init__(self, sessionmaker: async_sessionmaker[AsyncSession]) -> None:
        self._sessionmaker = sessionmaker

    async def candidates(self, internal_domains: tuple[str, ...]) -> tuple[Candidate, ...]:
        unlinked = (
            select(
                InteractionParticipant.email,
                InteractionParticipant.domain,
                # Any one name will do: the same address shows the same name.
                func.max(InteractionParticipant.display_name),
            )
            .where(
                InteractionParticipant.person_attio_id.is_(None),
                InteractionParticipant.domain.not_in(internal_domains),
            )
            .group_by(InteractionParticipant.email, InteractionParticipant.domain)
            .order_by(InteractionParticipant.email)
        )
        async with self._sessionmaker() as session:
            rows = (await session.execute(unlinked)).all()
            two_way = set((await session.execute(_two_way_senders())).scalars())
            attended = set((await session.execute(_meeting_attendees())).scalars())
        return tuple(
            Candidate(email, domain, name, email in two_way, email in attended)
            for email, domain, name in rows
            if email in two_way or email in attended
        )


def _two_way_senders() -> Select[tuple[str]]:
    """Addresses that wrote into a thread the team also wrote in."""
    sender = aliased(InteractionParticipant)
    inbound = aliased(Interaction)
    outbound = aliased(Interaction)
    return (
        select(sender.email)
        .join(inbound, inbound.id == sender.interaction_id)
        .join(
            outbound,
            and_(outbound.thread_id == inbound.thread_id, outbound.id != inbound.id),
        )
        .where(
            sender.role == Role.FROM.value,
            inbound.channel == Channel.EMAIL.value,
            inbound.direction == Direction.INBOUND.value,
            inbound.thread_id.is_not(None),
            outbound.channel == Channel.EMAIL.value,
            outbound.direction == Direction.OUTBOUND.value,
        )
        .distinct()
    )


def _meeting_attendees() -> Select[tuple[str]]:
    """Addresses on a meeting that was not cancelled. Declined guests never reach the table."""
    attendee = aliased(InteractionParticipant)
    meeting = aliased(Interaction)
    return (
        select(attendee.email)
        .join(meeting, meeting.id == attendee.interaction_id)
        .where(
            attendee.role == Role.ATTENDEE.value,
            meeting.channel == Channel.MEETING.value,
            meeting.cancelled.is_(False),
        )
        .distinct()
    )
