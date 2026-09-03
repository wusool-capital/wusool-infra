"""Pydantic schemas at the matching concept's external/application boundary.

No `MatchRunRead`/`MatchEvidenceRead`/`ApprovalRead` as separate schemas —
`MatchResultRead` below covers the run/candidate rows `match_results` holds
(see the Phase 3 handover doc's row-kind invariant). `MatchScoreRead` maps
the pre-existing deterministic scoring breakdown.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel

from app.modules.matching_engine.domain.matching.entities import FilterSkippedReason
from app.modules.matching_engine.domain.requirements import ConfidenceLevel, RequirementSource


class HardRequirementRead(BaseModel):
    model_config = {"from_attributes": True}

    criterion: str
    value: str | None
    source: RequirementSource
    confidence: ConfidenceLevel
    human_confirmed: bool


class SoftPreferenceRead(BaseModel):
    model_config = {"from_attributes": True}

    criterion: str
    value: str | None
    weight: float
    source: RequirementSource
    confidence: ConfidenceLevel


class RequirementProfileRead(BaseModel):
    model_config = {"from_attributes": True}

    hard_requirements: list[HardRequirementRead]
    soft_preferences: list[SoftPreferenceRead]
    strategic_thesis: str | None
    ideal_target_description: str | None
    scoring_rubric: dict[str, float]
    data_confidence: float


class FilterSkippedRead(BaseModel):
    model_config = {"from_attributes": True}

    criterion: str
    reason: FilterSkippedReason
    candidates_exempted: int


class MatchScoreRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    buyer_attio_id: str
    seller_attio_id: str
    score: Decimal
    # Deliberately loose/forward-compatible: no producer of these fields
    # exists yet to pin down a stricter shape.
    dims: dict | None = None
    reasoning: str | None = None
    citations: list | None = None
    generated_at: datetime


class MatchResultRead(BaseModel):
    model_config = {"from_attributes": True}

    id: uuid.UUID
    run_id: uuid.UUID
    rank: int | None = None
    seller_attio_id: str | None = None
    seller_org_name: str | None = None
    match_score: Decimal | None = None
    data_confidence: Decimal | None = None
    why_chosen_over_alternatives: str | None = None
    recommended_pitch: str | None = None
    risks_and_gaps: str | None = None
    status: str
    approved_by: str | None = None
    decision: str | None = None
    decided_at: datetime | None = None
    # Run-row-only fields (None on candidate rows) — see the row-kind
    # invariant in `infrastructure/models.py`.
    requirement_profile: RequirementProfileRead | None = None
    candidates_considered: int | None = None
    candidates_filtered: int | None = None
    filters_skipped: list[FilterSkippedRead] | None = None
    errors: dict | None = None


class MatchAnalysis(BaseModel):
    """View Full Analysis output (§21) — built entirely from persisted data,
    never re-running Bedrock.
    """

    run: MatchResultRead
    candidates: list[MatchResultRead]
    scores: list[MatchScoreRead]
