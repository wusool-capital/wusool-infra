"""The advisor's own typed context outranks stored CRM data for the same
criterion — "Egypt" typed against a CRM target of the US means Egypt. Kept
deterministic here so the override never depends on the LLM's discretion alone.
"""

from dataclasses import replace

from app.modules.matching_engine.domain.matching.scoring import canonical_criterion
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
