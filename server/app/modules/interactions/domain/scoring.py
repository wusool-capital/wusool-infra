"""Connection strength: points per touch, halved every `half_life_days`."""

from collections import defaultdict
from collections.abc import Sequence
from datetime import datetime

from app.modules.interactions.domain.model import (
    Channel,
    Direction,
    PairScore,
    ScoringRules,
    StrengthLabel,
    Touch,
)

_SECONDS_PER_DAY = 86_400


def age_days(touch: Touch, now: datetime) -> float:
    return max((now - touch.occurred_at).total_seconds() / _SECONDS_PER_DAY, 0.0)


def _points(touch: Touch, rules: ScoringRules) -> float:
    if touch.channel is Channel.MEETING:
        return rules.meeting_points
    if touch.direction is Direction.OUTBOUND:
        return rules.email_sent_points
    return rules.email_received_points


def _is_two_way(touches: Sequence[Touch], now: datetime, rules: ScoringRules) -> bool:
    recent = {
        t.direction
        for t in touches
        if t.channel is Channel.EMAIL and age_days(t, now) <= rules.two_way_window_days
    }
    return {Direction.INBOUND, Direction.OUTBOUND} <= recent


def score_pair(touches: Sequence[Touch], now: datetime, rules: ScoringRules) -> float:
    """Score for one team member and one contact; touches after `now` don't count yet."""
    past = [t for t in touches if t.occurred_at <= now]
    total = sum(_points(t, rules) * 0.5 ** (age_days(t, now) / rules.half_life_days) for t in past)
    return total * rules.two_way_bonus if _is_two_way(past, now, rules) else total


def score_pairs(
    touches: Sequence[Touch], now: datetime, rules: ScoringRules
) -> tuple[PairScore, ...]:
    """Every team member and contact pair, strongest first, ties broken by name."""
    by_pair: dict[tuple[str, str], list[Touch]] = defaultdict(list)
    for touch in touches:
        by_pair[(touch.team_member, touch.contact)].append(touch)
    scored = [
        PairScore(member, contact, score_pair(group, now, rules))
        for (member, contact), group in by_pair.items()
    ]
    return tuple(sorted(scored, key=lambda p: (-p.score, p.team_member, p.contact)))


def label_for(score: float, cutoffs: tuple[float, float, float, float]) -> StrengthLabel:
    """Lower bound inclusive, upper bound exclusive: a score of exactly 3 is Good."""
    return tuple(StrengthLabel)[sum(score >= cutoff for cutoff in cutoffs)]
