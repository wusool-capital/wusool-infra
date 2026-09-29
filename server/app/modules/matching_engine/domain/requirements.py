"""Requirement domain value objects (§5, §6). No database session or
SQLAlchemy import here — the extraction service builds these from Bedrock
output validated through `api/requirements.py`'s Pydantic contract.
"""

from dataclasses import dataclass, field
from typing import Literal

RequirementSource = Literal[
    "crm_field", "advisor_context", "llm_extracted", "llm_inferred", "unavailable"
]
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
class AdvisorLimits:
    """Money limits the advisor stated in their own context, USD. They
    replace the buyer role's stored check size / EV ceiling for this run."""

    ticket_min: float | None = None
    ticket_max: float | None = None
    ev_ceiling: float | None = None


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
    advisor_limits: AdvisorLimits = field(default_factory=AdvisorLimits)
