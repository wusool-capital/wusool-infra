"""The advisor's own typed context outranks stored CRM data for the same
criterion — "Egypt" typed against a CRM target of the US means Egypt. Kept
deterministic here so the override never depends on the LLM's discretion alone.
"""

import re
from dataclasses import replace

from app.modules.matching_engine.domain.matching.scoring import (
    canonical_criterion,
    is_monetary_criterion,
)
from app.modules.matching_engine.domain.requirements import RequirementProfile


def advisor_stated_values(profile: RequirementProfile) -> dict[str, tuple[str, ...]]:
    """Values the advisor explicitly stated, keyed by canonical criterion."""
    stated: dict[str, list[str]] = {}
    for requirement in profile.hard_requirements:
        canonical = canonical_criterion(requirement.criterion)
        if (
            requirement.source == "advisor_context"
            and requirement.human_confirmed
            and requirement.value
            and canonical
        ):
            stated.setdefault(canonical, []).append(requirement.value)
    return {criterion: tuple(values) for criterion, values in stated.items()}


def apply_advisor_overrides(profile: RequirementProfile) -> RequirementProfile:
    """Drops CRM-sourced requirements for any criterion the advisor restated,
    so a stale stored value can't eliminate sellers the advisor asked for."""
    overridden = set(advisor_stated_values(profile))
    if not overridden:
        return profile

    def is_superseded(criterion: str, source: str) -> bool:
        return source == "crm_field" and canonical_criterion(criterion) in overridden

    return replace(
        profile,
        hard_requirements=[
            h for h in profile.hard_requirements if not is_superseded(h.criterion, h.source)
        ],
        soft_preferences=[
            s for s in profile.soft_preferences if not is_superseded(s.criterion, s.source)
        ],
    )


_MONEY_MENTION = re.compile(r"(?:\$|usd\s*)\s*\d|\b\d[\d,.]*\s*(?:k|m|mn|b|bn)\b", re.IGNORECASE)

UNLABELLED_AMOUNT_NOTE = (
    "No ticket-size or EV limit applied: the amount you typed didn't say what it "
    'measures. Try e.g. "up to $10M tickets" or "EV cap $10M".'
)


def unlabelled_amount_note(advisor_context: str | None, profile: RequirementProfile) -> str | None:
    """A note for the advisor when their context holds a money amount that
    ended up as no limit at all — otherwise it is silently ignored. Skipped
    when the amount plausibly became a revenue/EBITDA requirement instead."""
    if not advisor_context or not _MONEY_MENTION.search(advisor_context):
        return None
    limits = profile.advisor_limits
    if any(v is not None for v in (limits.ticket_min, limits.ticket_max, limits.ev_ceiling)):
        return None
    requirements = [*profile.hard_requirements, *profile.soft_preferences]
    if any(r.source != "crm_field" and is_monetary_criterion(r.criterion) for r in requirements):
        return None
    return UNLABELLED_AMOUNT_NOTE
