"""Pydantic schemas validating Bedrock's own raw JSON output — never an
HTTP DTO. `ExtractedRequirementProfile` is the strict validation target for
Stage 1 extraction (§7); `ReasoningResult` is the strict contract Stage 3
reasoning output must validate against (§7, §15). Never trust raw LLM text
past this boundary.
"""

import re
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from app.modules.matching_engine.application.ports.llm_types import ExtractedRequirements
from app.modules.matching_engine.domain.matching.entities import (
    CandidateNarrative,
    ReasoningOutcome,
)
from app.modules.matching_engine.domain.matching.scoring import is_monetary_criterion
from app.modules.matching_engine.domain.requirements import (
    AdvisorLimits,
    HardRequirement,
    SoftPreference,
)
from app.modules.utilities.domain.money import parse_usd_amount

RequirementSource = Literal[
    "crm_field", "advisor_context", "llm_extracted", "llm_inferred", "unavailable"
]
ConfidenceLevel = Literal["high", "medium", "low"]

# The model sometimes writes the next field's tool-call syntax into a string,
# swallowing that field (seen live: `</thesis> <parameter name="ideal_target_description">`).
_LEAKED_MARKUP = re.compile(r"<\s*/?\s*(parameter|invoke)\b", re.IGNORECASE)


def _no_leaked_markup(value: str | None) -> str | None:
    if value is not None and _LEAKED_MARKUP.search(value):
        raise ValueError(
            "contains tool-call markup such as `<parameter name=...>`; put each "
            "field's text in its own JSON field, as plain text"
        )
    return value


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

    def to_domain(self) -> HardRequirement:
        return HardRequirement(
            criterion=self.criterion,
            value=self.value,
            source=self.source,
            confidence=self.confidence,
            human_confirmed=self.human_confirmed,
        )


class ExtractedSoftPreference(BaseModel):
    criterion: str
    value: str | None = None
    weight: float = Field(ge=0.0, le=1.0)
    source: RequirementSource
    confidence: ConfidenceLevel

    def to_domain(self) -> SoftPreference:
        return SoftPreference(
            criterion=self.criterion,
            value=self.value,
            weight=self.weight,
            source=self.source,
            confidence=self.confidence,
        )


class ExtractedAdvisorLimits(BaseModel):
    """Written `USD <amount>` like every other monetary value here; an
    unparseable one fails validation and triggers the output retry."""

    ticket_min: str | None = None
    ticket_max: str | None = None
    ev_ceiling: str | None = None

    @field_validator("ticket_min", "ticket_max", "ev_ceiling")
    @classmethod
    def must_be_usd_amount(cls, value: str | None) -> str | None:
        parse_usd_amount(value)
        return value

    def to_domain(self) -> AdvisorLimits:
        return AdvisorLimits(
            ticket_min=parse_usd_amount(self.ticket_min),
            ticket_max=parse_usd_amount(self.ticket_max),
            ev_ceiling=parse_usd_amount(self.ev_ceiling),
        )


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
    search_phrase: str | None = None

    @field_validator("strategic_thesis", "ideal_target_description", "search_phrase")
    @classmethod
    def no_leaked_markup(cls, value: str | None) -> str | None:
        return _no_leaked_markup(value)

    def monetary_issue(self) -> str | None:
        """Names the first monetary requirement not written as `USD <amount>`."""
        rows = [
            *(("hard_requirements", i, r) for i, r in enumerate(self.hard_requirements)),
            *(("soft_preferences", i, r) for i, r in enumerate(self.soft_preferences)),
        ]
        for field_name, index, row in rows:
            if row.value is None or not is_monetary_criterion(row.criterion):
                continue
            try:
                parse_usd_amount(row.value)
            except ValueError as exc:
                return f"{field_name}[{index}].value (criterion {row.criterion!r}): {exc}"
        return None

    def to_domain(self) -> ExtractedRequirements:
        return ExtractedRequirements(
            hard_requirements=[h.to_domain() for h in self.hard_requirements],
            soft_preferences=[s.to_domain() for s in self.soft_preferences],
            strategic_thesis=self.strategic_thesis,
            ideal_target_description=self.ideal_target_description,
            scoring_rubric=dict(self.scoring_rubric),
            data_confidence=self.data_confidence,
            advisor_limits=self.advisor_limits.to_domain(),
            search_phrase=self.search_phrase,
        )


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

    @field_validator(
        "why_it_matches",
        "why_chosen_over_alternatives",
        "recommended_pitch",
        "risks_and_gaps",
        "confidence_narrative",
    )
    @classmethod
    def no_leaked_markup(cls, value: str) -> str:
        _no_leaked_markup(value)
        return value

    def to_domain(self) -> CandidateNarrative:
        return CandidateNarrative(
            seller_role_id=self.seller_role_id,
            why_it_matches=self.why_it_matches,
            why_chosen_over_alternatives=self.why_chosen_over_alternatives,
            recommended_pitch=self.recommended_pitch,
            risks_and_gaps=self.risks_and_gaps,
            confidence_narrative=self.confidence_narrative,
        )


class ReasoningResult(BaseModel):
    candidates: list[ReasoningCandidateResult] = Field(default_factory=list)

    def to_domain(self) -> ReasoningOutcome:
        return ReasoningOutcome(candidates=[c.to_domain() for c in self.candidates])
