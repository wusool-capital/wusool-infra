"""Framework-free value types for the interactions engine."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class Channel(StrEnum):
    EMAIL = "email"
    MEETING = "meeting"


class Direction(StrEnum):
    INBOUND = "inbound"
    OUTBOUND = "outbound"


class Role(StrEnum):
    FROM = "from"
    TO = "to"
    CC = "cc"
    ATTENDEE = "attendee"


class StrengthLabel(StrEnum):
    # Declaration order is weakest to strongest; `label_for` indexes into it.
    VERY_WEAK = "Very weak"
    WEAK = "Weak"
    GOOD = "Good"
    STRONG = "Strong"
    VERY_STRONG = "Very strong"


@dataclass(frozen=True)
class ScoringRules:
    """Tunable during the shadow week; defaults are the plan's starting values."""

    email_sent_points: float = 1.0
    email_received_points: float = 1.5
    meeting_points: float = 4.0
    half_life_days: float = 90.0
    two_way_bonus: float = 1.5
    two_way_window_days: int = 180
    next_window_days: int = 180
    # Lower bounds of Weak, Good, Strong and Very strong.
    cutoffs: tuple[float, float, float, float] = (1.0, 3.0, 7.0, 15.0)


@dataclass(frozen=True)
class Touch:
    """One email or meeting between a team member and one outside contact."""

    dedupe_key: str
    team_member: str
    contact: str
    channel: Channel
    # Relative to the team: outbound when a team member sent it. None for meetings.
    direction: Direction | None
    occurred_at: datetime
    subject: str | None = None
    # The team member's role on the item; drives the owner rule.
    team_role: Role | None = None


@dataclass(frozen=True)
class PairScore:
    team_member: str
    contact: str
    score: float


@dataclass(frozen=True)
class InteractionSummary:
    first_interaction_at: datetime | None
    last_interaction_at: datetime | None
    next_interaction_at: datetime | None
    first_email_interaction_at: datetime | None
    last_email_interaction_at: datetime | None
    first_calendar_interaction_at: datetime | None
    last_calendar_interaction_at: datetime | None
    next_calendar_interaction_at: datetime | None
    last_interaction_channel: Channel | None
    last_interaction_owner: str | None
    last_interaction_subject: str | None
    strongest_connection_user: str | None
    connection_strength: StrengthLabel | None
    score: float


@dataclass(frozen=True)
class RawItem:
    """What the ignore filter needs to know about one fetched message or event."""

    channel: Channel
    # Normalized addresses of everyone on the item, team members included.
    participants: tuple[str, ...]
    labels: frozenset[str] = frozenset()
    subject: str | None = None
    auto_submitted: str | None = None
    # A List-Unsubscribe header marks a mailing, not a conversation.
    bulk: bool = False
    all_day: bool = False
    cancelled: bool = False
    # The mailbox owner's own calendar response.
    team_declined: bool = False
