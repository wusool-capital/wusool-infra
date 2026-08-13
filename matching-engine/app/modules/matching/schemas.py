"""Pydantic schemas at the matching module's external/application boundary.

No `MatchRunRead`/`MatchEvidenceRead`/`ApprovalRead` — there is no
match_runs/matches/match_evidence/approvals table (see the Phase 2 plan's
schema-gap note). `MatchScoreRead` maps the only match-related table that
exists.
"""

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class MatchScoreRead(BaseModel):
    model_config = {"from_attributes": True}

    id: str
    buyer_attio_id: str
    seller_attio_id: str
    score: Decimal
    # Deliberately loose/forward-compatible: no producer of these fields
    # exists yet to pin down a stricter shape.
    dims: dict | None = None
    reasoning: str | None = None
    citations: list | None = None
    generated_at: datetime
