"""Buyer domain value objects. No database session or SQLAlchemy import here —
these are what other modules (e.g. matching) should depend on instead of the
buyer module's ORM model.
"""

from dataclasses import dataclass

from app.shared.types import Money


@dataclass(frozen=True)
class BuyerContext:
    buyer_role_id: str
    org_attio_id: str
    org_name: str
    model: str | None
    mandate_status: str | None
    ebitda_floor: Money | None
    check_size_min: Money | None
    check_size_max: Money | None
    ev_ceiling: Money | None
    deal_structure_tolerance: str | None
    earnout_tolerance: str | None
    profitable_only: bool | None
    investment_strategy: str | None
    notes: str | None
    contact_person_id: str | None
