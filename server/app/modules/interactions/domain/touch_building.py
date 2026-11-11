"""Turning stored interactions into the `Touch`es that scoring reads, grouped by Organization."""

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import datetime

from app.modules.interactions.domain.addresses import is_internal, team_member_of
from app.modules.interactions.domain.model import Channel, Direction, Role, Touch

# Sender first, then To, then CC or attendee, as the owner rule reads them.
_ROLE_ORDER = (Role.FROM, Role.TO, Role.CC, Role.ATTENDEE)


@dataclass(frozen=True)
class StoredParticipant:
    email: str
    role: Role
    organization_id: str | None


@dataclass(frozen=True)
class StoredItem:
    """One interaction as held in one mailbox, with every participant row."""

    mailbox: str
    dedupe_key: str
    channel: Channel
    direction: Direction | None
    occurred_at: datetime
    subject: str | None
    participants: tuple[StoredParticipant, ...]


def touches_by_organization(
    items: Iterable[StoredItem], internal_domains: tuple[str, ...]
) -> dict[str, tuple[Touch, ...]]:
    """One touch per item and outside contact, even when the contact is on both To and CC."""
    grouped: dict[str, list[Touch]] = defaultdict(list)
    for item in items:
        team_member = team_member_of(item.mailbox, internal_domains)
        # Participants are stored folded, the mailbox is not, so fold before comparing.
        team_roles = {p.role for p in item.participants if p.email == team_member}
        team_role = next((r for r in _ROLE_ORDER if r in team_roles), None)
        seen: set[str] = set()
        for participant in item.participants:
            if (
                participant.organization_id is None
                or is_internal(participant.email, internal_domains)
                or participant.email in seen
            ):
                continue
            seen.add(participant.email)
            grouped[participant.organization_id].append(
                Touch(
                    dedupe_key=item.dedupe_key,
                    team_member=team_member,
                    contact=participant.email,
                    channel=item.channel,
                    direction=item.direction,
                    occurred_at=item.occurred_at,
                    subject=item.subject,
                    team_role=team_role,
                )
            )
    return {org: tuple(touches) for org, touches in grouped.items()}
