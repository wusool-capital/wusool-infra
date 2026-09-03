"""Matching domain value objects. No database session or SQLAlchemy import here.

`MatchScoreResult` mirrors the real `match_scores` row 1:1 — there's no
separate match_runs/matches/match_evidence concept in the current schema
(see the Phase 2 plan's schema-gap note), so this is the entirety of a
persisted match result today.
"""

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Literal

from app.modules.matching_engine.domain.requirements import RequirementProfile, RequirementSource
from app.modules.matching_engine.domain.sellers import SellerCandidate


@dataclass(frozen=True)
class MatchScoreResult:
    id: str
    buyer_attio_id: str
    seller_attio_id: str
    score: Decimal
    dims: dict
    reasoning: str | None
    citations: list
    generated_at: datetime


@dataclass(frozen=True)
class CriterionScore:
    """One row of the deterministic Stage 2 breakdown (§9, §11) — the
    persisted equivalent lives in `match_scores.dims`.
    """

    criterion: str
    criterion_type: Literal["hard", "soft"]
    weight: float | None
    result: str
    data_backing: RequirementSource


@dataclass(frozen=True)
class DataConfidence:
    """0-100 scale, matching `match_score`'s convention — a separate signal
    from `overall_score`, never combined into one number (§12).
    """

    value: float
    applicable_criteria: int
    total_criteria: int


@dataclass(frozen=True)
class EvidenceReference:
    """Grounds an LLM claim in something the reasoning call was actually
    given (§16) — never a fabricated document/chunk id.
    """

    claim: str
    source_type: Literal[
        "attio_field",
        "call_transcript",
        "website",
        "teaser",
        "investment_memorandum",
        "mandate",
        "notes_field",
    ]
    source_ref: str | None
    confidence: Literal["confirmed", "inferred"]


@dataclass(frozen=True)
class CandidateScore:
    """Stage 2 `ScoringEngine.score(...)`'s output — the deterministic
    breakdown for one buyer/seller pair, before persistence.
    """

    buyer_role_id: str
    seller_role_id: str
    overall_score: float
    confidence: DataConfidence
    criteria: list[CriterionScore] = field(default_factory=list)
    evidence: list[EvidenceReference] = field(default_factory=list)


@dataclass(frozen=True)
class CandidateNarrative:
    """Stage 3 (§15-16) per-candidate qualitative narrative — the LLM is
    responsible for this only, never the numeric score, hard-filter
    decisions, entity IDs, or database writes.
    """

    seller_role_id: str
    why_it_matches: str
    why_chosen_over_alternatives: str
    recommended_pitch: str
    risks_and_gaps: str
    confidence_narrative: str


@dataclass(frozen=True)
class ReasoningOutcome:
    candidates: list[CandidateNarrative] = field(default_factory=list)


FilterSkippedReason = Literal["no_mapping", "unconfirmed_llm_extraction", "no_populated_field"]


@dataclass(frozen=True)
class FilterSkipped:
    """One hard requirement that Stage 1 filtering couldn't fully enforce
    across the candidate batch — see `apply_structured_filters`'s docstring
    for the exemption rule."""

    criterion: str
    reason: FilterSkippedReason
    candidates_exempted: int


@dataclass(frozen=True)
class CandidateBatch:
    """The §35 future-proofing seam's shared return shape — Branch 2 can add
    a `HybridCandidateRetriever` implementing the same Port without changing
    anything above it (the orchestrator, scoring, reasoning)."""

    passed: list[SellerCandidate]
    filters_skipped: list[FilterSkipped]
    considered: int


@dataclass(frozen=True)
class MatchResultEntity:
    """Mirrors `match_results` 1:1 — the table (and `api/matching.py`'s
    `MatchResultRead` schema) already treat run rows (`rank IS NULL`) and
    candidate rows (`rank IS NOT NULL`) as one unified shape (the "row-kind
    invariant"), so this is one domain type, not two. `buyer_org_name`/
    `seller_org_name` are flattened here from the ORM's
    `buyer_organization`/`seller_organization` relationship by the mapper —
    application code never touches that relationship directly.
    """

    id: str
    run_id: str
    rank: int | None
    status: str
    buyer_attio_id: str
    buyer_role_id: str
    buyer_org_name: str | None
    seller_attio_id: str | None
    seller_role_id: str | None
    seller_org_name: str | None
    match_score_id: str | None
    match_score: float | None
    data_confidence: float | None
    why_chosen_over_alternatives: str | None
    recommended_pitch: str | None
    risks_and_gaps: str | None
    approved_by: str | None
    decision: str | None
    decision_notes: str | None
    decided_at: datetime | None
    requested_by: str | None
    model_version: str | None
    requirement_profile_version: int | None
    requirement_profile: RequirementProfile | None
    candidates_considered: int | None
    candidates_filtered: int | None
    filters_skipped: list[FilterSkipped] | None
    final_candidate_ids: list[str] | None
    execution_duration_ms: int | None
    errors: dict | None
    started_at: datetime
    completed_at: datetime | None


@dataclass(frozen=True)
class MatchAnalysisData:
    """View Full Analysis (§21) — built entirely from persisted data, never
    re-running Bedrock. The api layer converts this into `api/matching.py`'s
    `MatchAnalysis` Pydantic schema at the boundary; `application/` never
    touches that schema directly.
    """

    run: MatchResultEntity
    candidates: list[MatchResultEntity]
    scores: list[MatchScoreResult]
