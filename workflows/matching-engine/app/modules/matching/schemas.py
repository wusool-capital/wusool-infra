"""Pydantic schemas at the matching module's external/application boundary.

No `MatchRunRead`/`MatchEvidenceRead`/`ApprovalRead` as separate schemas —
`MatchResultRead` below covers the run/candidate rows `match_results` holds
(see the Phase 3 handover doc's row-kind invariant). `MatchScoreRead` maps
the pre-existing deterministic scoring breakdown. `ReasoningResult` is the
strict Pydantic contract Bedrock's Stage 3 reasoning output must validate
against (§7, §15) — never trust raw LLM text past this boundary.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


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
    requirement_profile: dict | None = None
    candidates_considered: int | None = None
    candidates_filtered: int | None = None
    filters_skipped: list | None = None
    errors: dict | None = None


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


class MatchAnalysis(BaseModel):
    """View Full Analysis output (§21) — built entirely from persisted data,
    never re-running Bedrock.
    """

    run: MatchResultRead
    candidates: list[MatchResultRead]
    scores: list[MatchScoreRead]
