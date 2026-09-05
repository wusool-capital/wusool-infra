"""Pydantic schemas validating Bedrock's own raw JSON output — never an
HTTP DTO. `ExtractedRequirementProfile` is the strict validation target for
Stage 1 extraction (§7); `ReasoningResult` is the strict contract Stage 3
reasoning output must validate against (§7, §15). Never trust raw LLM text
past this boundary.
"""

from typing import Literal

from pydantic import BaseModel, Field, model_validator

RequirementSource = Literal["crm_field", "llm_extracted", "llm_inferred", "unavailable"]
ConfidenceLevel = Literal["high", "medium", "low"]


class ExtractedHardRequirement(BaseModel):
    criterion: str
    value: str | None = None
    source: RequirementSource
    confidence: ConfidenceLevel
    human_confirmed: bool = False

    @model_validator(mode="after")
    def prevent_unverified_confirmation(self) -> "ExtractedHardRequirement":
        if self.source != "crm_field":
            self.human_confirmed = False
        return self


class ExtractedSoftPreference(BaseModel):
    criterion: str
    value: str | None = None
    weight: float = Field(ge=0.0, le=1.0)
    source: RequirementSource
    confidence: ConfidenceLevel


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
