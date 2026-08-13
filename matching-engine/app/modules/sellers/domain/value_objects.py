"""Seller domain value objects. No database session or SQLAlchemy import here."""

from dataclasses import dataclass

from app.shared.types import Money


@dataclass(frozen=True)
class SellerCandidate:
    seller_role_id: str
    org_attio_id: str
    org_name: str
    outreach_tier: str | None
    relationship_status: str | None
    est_revenue: Money | None
    est_ebitda: Money | None
    valuation_low: Money | None
    valuation_mid: Money | None
    valuation_high: Money | None
