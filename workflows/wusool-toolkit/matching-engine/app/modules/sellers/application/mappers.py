"""Converts seller ORM rows into infra-independent domain objects."""

from wusool_db.models import SellerRole

from app.modules.sellers.domain.value_objects import SellerCandidate
from app.shared.types import Money


def _money(value: dict | None) -> Money | None:
    return Money(**value) if value else None


def _float(value) -> float | None:
    """seller_roles.readiness_score is NUMERIC in Postgres, which SQLAlchemy
    maps to Decimal — the domain/API layer wants plain float (see
    SellerCandidate/schemas.py), so convert at this ORM-to-domain boundary
    rather than changing either side to match the other."""
    return float(value) if value is not None else None


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
