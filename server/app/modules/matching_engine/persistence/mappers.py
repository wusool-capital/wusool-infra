"""ORM row <-> domain entity translation, one function per concept. This is
where the "domain must not import SQLAlchemy" boundary is actually enforced:
application/domain code consumes the domain dataclasses below, never the
`app.models` ORM classes directly.
"""

from sqlalchemy import inspect

from app.models import BuyerRole, MatchResult, MatchScore, SellerRole
from app.modules.matching_engine.domain.buyers import BuyerContext
from app.modules.matching_engine.domain.matching.entities import (
    MatchResultEntity,
    MatchScoreResult,
)
from app.modules.matching_engine.domain.sellers import SellerCandidate
from app.modules.utilities.domain.money import Money


def _money(value: dict | None) -> Money | None:
    return Money(**value) if value else None


def _float(value) -> float | None:
    """seller_roles.readiness_score is NUMERIC in Postgres, which SQLAlchemy
    maps to Decimal — the domain/API layer wants plain float (see
    SellerCandidate/schemas.py), so convert at this ORM-to-domain boundary
    rather than changing either side to match the other."""
    return float(value) if value is not None else None


def to_buyer_context(role: BuyerRole) -> BuyerContext:
    return BuyerContext(
        buyer_role_id=str(role.id),
        org_attio_id=role.org_attio_id,
        org_name=role.organization.name,
        model=role.model,
        mandate_status=role.mandate_status,
        ebitda_floor=_money(role.ebitda_floor),
        check_size_min=_money(role.check_size_min),
        check_size_max=_money(role.check_size_max),
        ev_ceiling=_money(role.ev_ceiling),
        deal_structure_tolerance=role.deal_structure_tolerance,
        earnout_tolerance=role.earnout_tolerance,
        profitable_only=role.profitable_only,
        investment_strategy=role.investment_strategy,
        notes=role.notes,
        contact_person_id=role.key_contact_attio_id,
        org_hq_country=role.organization.hq_country,
        org_sector_focus=list(role.organization.sector_focus or []),
    )


def to_seller_candidate(role: SellerRole) -> SellerCandidate:
    return SellerCandidate(
        seller_role_id=str(role.id),
        org_attio_id=role.org_attio_id,
        org_name=role.organization.name,
        outreach_tier=role.outreach_tier,
        relationship_status=role.relationship_status,
        appetite_signal=role.appetite_signal,
        readiness_score=_float(role.readiness_score),
        est_revenue=_money(role.est_revenue),
        est_ebitda=_money(role.est_ebitda),
        valuation_low=_money(role.valuation_low),
        valuation_mid=_money(role.valuation_mid),
        valuation_high=_money(role.valuation_high),
        geographic_focus=list(role.organization.geographic_focus),
        sector_focus=list(role.organization.sector_focus),
        hq_country=role.organization.hq_country,
        client_type=role.organization.client_type,
    )


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


def _loaded_org_name(row: MatchResult, relationship_attr: str) -> str | None:
    """Reads `row.<relationship_attr>.name` only if that relationship is
    already loaded — accessing an unloaded relationship on an `AsyncSession`
    row (e.g. right after `create_run`'s insert, before any eager-load
    query) raises rather than lazy-loading. Callers that need the name
    reliably populated must eager-load it first (as `get_run`/`get_candidates`
    already do); this just keeps the mapper safe to call unconditionally.
    """
    if relationship_attr in inspect(row).unloaded:
        return None
    organization = getattr(row, relationship_attr)
    return organization.name if organization else None


def to_match_result_entity(row: MatchResult) -> MatchResultEntity:
    return MatchResultEntity(
        id=str(row.id),
        run_id=str(row.run_id),
        rank=row.rank,
        status=row.status,
        buyer_attio_id=row.buyer_attio_id,
        buyer_role_id=str(row.buyer_role_id),
        buyer_org_name=_loaded_org_name(row, "buyer_organization"),
        seller_attio_id=row.seller_attio_id,
        seller_role_id=str(row.seller_role_id) if row.seller_role_id else None,
        seller_org_name=_loaded_org_name(row, "seller_organization"),
        match_score_id=str(row.match_score_id) if row.match_score_id else None,
        match_score=_float(row.match_score),
        data_confidence=_float(row.data_confidence),
        why_chosen_over_alternatives=row.why_chosen_over_alternatives,
        recommended_pitch=row.recommended_pitch,
        risks_and_gaps=row.risks_and_gaps,
        approved_by=row.approved_by,
        decision=row.decision,
        decision_notes=row.decision_notes,
        decided_at=row.decided_at,
        requested_by=row.requested_by,
        model_version=row.model_version,
        requirement_profile_version=row.requirement_profile_version,
        requirement_profile=row.requirement_profile,
        candidates_considered=row.candidates_considered,
        candidates_filtered=row.candidates_filtered,
        filters_skipped=row.filters_skipped,
        final_candidate_ids=row.final_candidate_ids,
        execution_duration_ms=row.execution_duration_ms,
        errors=row.errors,
        started_at=row.started_at,
        completed_at=row.completed_at,
    )
