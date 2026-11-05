"""The Attio relationship fields for one Person or Organization."""

from collections.abc import Iterable, Sequence
from datetime import datetime, timedelta

from app.modules.interactions.domain.model import (
    Channel,
    InteractionSummary,
    Role,
    ScoringRules,
    Touch,
)
from app.modules.interactions.domain.scoring import label_for, score_pairs

# Sender first, then To, then CC or attendee; a remaining tie goes to the stronger pair.
_ROLE_RANK = {Role.FROM: 0, Role.TO: 1, Role.CC: 2, Role.ATTENDEE: 2}


def _rank(touch: Touch) -> int:
    return _ROLE_RANK[touch.team_role] if touch.team_role else 3


def _earliest(touches: Iterable[Touch]) -> datetime | None:
    return min((t.occurred_at for t in touches), default=None)


def _latest(touches: Iterable[Touch]) -> datetime | None:
    return max((t.occurred_at for t in touches), default=None)


def summarize(touches: Sequence[Touch], now: datetime, rules: ScoringRules) -> InteractionSummary:
    """`touches` are every row linked to the record, one per team member and contact."""
    past = [t for t in touches if t.occurred_at <= now]
    horizon = now + timedelta(days=rules.next_window_days)
    upcoming = [
        t for t in touches if t.channel is Channel.MEETING and now < t.occurred_at <= horizon
    ]
    emails = [t for t in past if t.channel is Channel.EMAIL]
    meetings = [t for t in past if t.channel is Channel.MEETING]

    pairs = score_pairs(past, now, rules)
    strongest = pairs[0] if pairs else None
    pair_score = {(p.team_member, p.contact): p.score for p in pairs}

    last = max(past, key=lambda t: (t.occurred_at, t.dedupe_key), default=None)
    owner = None
    if last is not None:
        # The same item sits in every mailbox it reached, so pick one owner per dedupe key.
        same_item = [t for t in past if t.dedupe_key == last.dedupe_key]
        owner = min(
            same_item,
            key=lambda t: (_rank(t), -pair_score[(t.team_member, t.contact)], t.team_member),
        ).team_member

    return InteractionSummary(
        first_interaction_at=_earliest(past),
        last_interaction_at=_latest(past),
        next_interaction_at=_earliest(upcoming),
        first_email_interaction_at=_earliest(emails),
        last_email_interaction_at=_latest(emails),
        first_calendar_interaction_at=_earliest(meetings),
        last_calendar_interaction_at=_latest(meetings),
        next_calendar_interaction_at=_earliest(upcoming),
        last_interaction_channel=last.channel if last else None,
        last_interaction_owner=owner,
        last_interaction_subject=last.subject if last else None,
        strongest_connection_user=strongest.team_member if strongest else None,
        connection_strength=label_for(strongest.score, rules.cutoffs) if strongest else None,
        score=strongest.score if strongest else 0.0,
    )
