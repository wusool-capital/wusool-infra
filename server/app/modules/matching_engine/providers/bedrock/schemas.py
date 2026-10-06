"""Pydantic schemas validating Bedrock's own raw JSON output — never an
HTTP DTO. `ExtractedRequirementProfile` is the strict validation target for
Stage 1 extraction (§7); `ReasoningResult` is the strict contract Stage 3
reasoning output must validate against (§7, §15). Never trust raw LLM text
past this boundary.
"""

from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.utilities.domain.money import parse_usd_amount

RequirementSource = Literal[
    "crm_field", "advisor_context", "llm_extracted", "llm_inferred", "unavailable"
]
ConfidenceLevel = Literal["high", "medium", "low"]

# Only these come from a human: the CRM record, or what the advisor typed for this run.
_CONFIRMABLE_SOURCES: frozenset[str] = frozenset({"crm_field", "advisor_context"})


class ExtractedHardRequirement(BaseModel):
    criterion: str
    value: str | None = None
    source: RequirementSource
    confidence: ConfidenceLevel
    human_confirmed: bool = False

    @model_validator(mode="after")
    def prevent_unverified_confirmation(self) -> "ExtractedHardRequirement":
        if self.source not in _CONFIRMABLE_SOURCES:
            self.human_confirmed = False
        return self


class ExtractedSoftPreference(BaseModel):
    criterion: str
    value: str | None = None
    weight: float = Field(ge=0.0, le=1.0)
    source: RequirementSource
    confidence: ConfidenceLevel


class ExtractedAdvisorLimits(BaseModel):
    """Written `USD <amount>` like every other monetary value here; an
    unparseable one fails validation and triggers the repair retry."""

    ticket_min: str | None = None
    ticket_max: str | None = None
    ev_ceiling: str | None = None

    @field_validator("ticket_min", "ticket_max", "ev_ceiling")
    @classmethod
    def must_be_usd_amount(cls, value: str | None) -> str | None:
        parse_usd_amount(value)
        return value


class ExtractedRequirementProfile(BaseModel):
    """The LLM must never invent CRM fields — absent information is
    `Unknown`/`Partially known` at higher layers, never a fabricated value.
    """

    hard_requirements: list[ExtractedHardRequirement] = Field(default_factory=list)
    soft_preferences: list[ExtractedSoftPreference] = Field(default_factory=list)
    strategic_thesis: str | None = None
    ideal_target_description: str | None = None
    scoring_rubric: dict[str, float] = Field(default_factory=dict)
    data_confidence: float = Field(ge=0.0, le=1.0)
    advisor_limits: ExtractedAdvisorLimits = Field(default_factory=ExtractedAdvisorLimits)


class ReasoningCandidateResult(BaseModel):
    """Per-candidate Stage 3 output (§15). The LLM is responsible for the
    qualitative narrative only — never the numeric score, hard-filter
    decisions, entity IDs, or database writes.
    """

    seller_role_id: str
    why_it_matches: str
    why_chosen_over_alternatives: str
    recommended_pitch: str
    risks_and_gaps: str
    confidence_narrative: str


class ReasoningResult(BaseModel):
    candidates: list[ReasoningCandidateResult] = Field(default_factory=list)
