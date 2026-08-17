"""Converts buyer ORM rows into infra-independent domain objects.

This is where the "matching domain must not import SQLAlchemy" boundary is
actually enforced: matching consumes `BuyerContext`, never `BuyerRole`.
"""

from app.modules.buyers.domain.value_objects import BuyerContext
from wusool_db.models import BuyerRole
from app.shared.types import Money


def _money(value: dict | None) -> Money | None:
    return Money(**value) if value else None


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
    )
