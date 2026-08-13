"""Matching domain value objects. No database session or SQLAlchemy import here.

`MatchScoreResult` mirrors the real `match_scores` row 1:1 — there's no
separate match_runs/matches/match_evidence concept in the current schema
(see the Phase 2 plan's schema-gap note), so this is the entirety of a
persisted match result today.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


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
