"""Converts seller ORM rows into infra-independent domain objects."""

from app.modules.sellers.domain.value_objects import SellerCandidate
from app.modules.sellers.infrastructure.models import SellerRole
from app.shared.types import Money


def _money(value: dict | None) -> Money | None:
    return Money(**value) if value else None


def to_seller_candidate(role: SellerRole) -> SellerCandidate:
    return SellerCandidate(
        seller_role_id=str(role.id),
        org_attio_id=role.org_attio_id,
        org_name=role.organization.name,
        outreach_tier=role.outreach_tier,
        relationship_status=role.relationship_status,
        est_revenue=_money(role.est_revenue),
        est_ebitda=_money(role.est_ebitda),
        valuation_low=_money(role.valuation_low),
        valuation_mid=_money(role.valuation_mid),
        valuation_high=_money(role.valuation_high),
    )
