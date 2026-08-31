"""Pydantic schemas for structured LLM requirement-extraction input/output.

`ExtractedRequirementProfile` is the strict validation target for Bedrock's
raw JSON output (§7) — never trust raw LLM text past this boundary. Source
values use `Literal`, not a rigid enum, so a legitimate new value doesn't
become unreadable.
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
