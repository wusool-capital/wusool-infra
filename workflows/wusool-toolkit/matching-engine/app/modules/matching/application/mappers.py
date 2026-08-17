"""Converts match-score ORM rows into infra-independent domain objects."""

from app.modules.matching.domain.value_objects import MatchScoreResult
from wusool_db.models import MatchScore


def to_match_score_result(row: MatchScore) -> MatchScoreResult:
    return MatchScoreResult(
        id=str(row.id),
        buyer_attio_id=row.buyer_attio_id,
        seller_attio_id=row.seller_attio_id,
        score=row.score,
        dims=row.dims,
        reasoning=row.reasoning,
        citations=row.citations,
        generated_at=row.generated_at,
    )
