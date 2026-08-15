"""Requirement domain value objects (§5, §6). No database session or
SQLAlchemy import here — the extraction service builds these from Bedrock
output validated through `requirements/schemas.py`'s Pydantic contract.
"""

from dataclasses import dataclass
from typing import Literal

RequirementSource = Literal["crm_field", "llm_extracted", "llm_inferred", "unavailable"]
ConfidenceLevel = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class HardRequirement:
    criterion: str
    value: str | None
    source: RequirementSource
    confidence: ConfidenceLevel
    human_confirmed: bool


@dataclass(frozen=True)
class SoftPreference:
    criterion: str
    value: str | None
    weight: float
    source: RequirementSource
    confidence: ConfidenceLevel


@dataclass(frozen=True)
class RequirementProfile:
    hard_requirements: list[HardRequirement]
    soft_preferences: list[SoftPreference]
    strategic_thesis: str | None
    ideal_target_description: str | None
    scoring_rubric: dict[str, float]
    data_confidence: float
    generated_by_model: str
    version: int
