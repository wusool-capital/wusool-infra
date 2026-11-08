"""Dataclasses referenced by `application/ports/llm.py`'s `BedrockClient`
Protocol — kept apart from the Protocol itself per convention."""

from dataclasses import dataclass

from app.modules.matching_engine.domain.requirements import (
    AdvisorLimits,
    HardRequirement,
    SoftPreference,
)


@dataclass(frozen=True)
class InferenceConfig:
    """Bedrock inference parameters — from `Settings`, never hardcoded."""

    temperature: float
    max_tokens: int
    top_p: float


@dataclass(frozen=True)
class ExtractedRequirements:
    """Stage 1 extraction as the model returned it: schema-valid, but not yet
    checked against CRM vocabularies or the advisor's own words."""

    hard_requirements: list[HardRequirement]
    soft_preferences: list[SoftPreference]
    strategic_thesis: str | None
    ideal_target_description: str | None
    scoring_rubric: dict[str, float]
    data_confidence: float
    advisor_limits: AdvisorLimits
    search_phrase: str | None
