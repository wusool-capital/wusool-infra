"""Seller domain value objects. No database session or SQLAlchemy import here."""

from dataclasses import dataclass, field

from app.shared.types import MeetingNote, Money


@dataclass(frozen=True)
class SellerCandidate:
    seller_role_id: str
    org_attio_id: str
    org_name: str
    outreach_tier: str | None
    relationship_status: str | None
    appetite_signal: str | None
    readiness_score: float | None
    est_revenue: Money | None
    est_ebitda: Money | None
    valuation_low: Money | None
    valuation_mid: Money | None
    valuation_high: Money | None
    # Organization-side structured signals (§10) — sparse, per Phase 2's
    # NULL-is-normal rule.
    geographic_focus: list[str] = field(default_factory=list)
    sector_focus: list[str] = field(default_factory=list)
    hq_country: str | None = None
    client_type: str | None = None
    # Populated only for shortlisted candidates, only when
    # settings.enable_seller_meeting_notes is on (§ use_cases.py) — narrative
    # context for the reasoning prompt only, never scoring/filtering input.
    meeting_notes: list[MeetingNote] = field(default_factory=list)
