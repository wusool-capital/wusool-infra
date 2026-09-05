"""Buyer domain value objects. No database session or SQLAlchemy import here —
these are what other concepts (e.g. matching) should depend on instead of the
buyer concept's ORM model.
"""

from dataclasses import dataclass, field

from app.modules.matching_engine.domain.meetings import MeetingNote
from app.modules.utilities.domain.money import Money


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
    earnout_tolerance: bool | None
    profitable_only: bool | None
    investment_strategy: str | None
    notes: str | None
    contact_person_id: str | None
    meeting_notes: list[MeetingNote] = field(default_factory=list)
    # Organization-derived fields, needed only by the search-result view
    # (`application/buyers.py`'s `BuyerCandidate`) — optional/defaulted so
    # every other construction of `BuyerContext` is unaffected.
    org_hq_country: str | None = None
    org_sector_focus: list[str] = field(default_factory=list)
