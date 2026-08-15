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

from app.modules.requirements.domain.value_objects import RequirementSource


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
