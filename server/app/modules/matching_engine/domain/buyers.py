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
    # `buyer_roles` columns that exist in Postgres but were never carried
    # into this object — found 2026-09-14 tracing why a buyer with a real,
    # populated `target_geography` still produced an unrestricted seller
    # search: `BuyerRequirementExtractionService._build_prompt` can only see
    # what's on this dataclass, and these were silently absent from it
    # entirely (not just from the prompt). `target_geography` is the
    # structured value for the `geography` criterion; `ebitda_ceiling` is
    # `ebitda_floor`'s sibling bound, same JSONB money shape, added in the
    # same migration. The rest are free-text qualitative signal with no
    # single criterion of their own — folded into the prompt's context
    # section rather than `known_fields`.
    # These two replaced `target_geography` on 2026-09-26, and both must reach
    # the prompt: the bug above was a populated geography field the extractor
    # could not see. Two fields now, same trap, twice the surface.
    target_region: list[str] = field(default_factory=list)
    target_country: list[str] = field(default_factory=list)
    ebitda_ceiling: Money | None = None
    notable_investments: str | None = None
    key_personnel: str | None = None
    acquisition_enrichment: str | None = None
    prior_gcc_acquisition: str | None = None
    # Organization-derived fields, needed only by the search-result view
    # (`application/buyers.py`'s `BuyerCandidate`) — optional/defaulted so
    # every other construction of `BuyerContext` is unaffected. `org_hq_country`
    # is the buyer's own HQ, not their target market — never treat it as a
    # `geography` criterion value (a UK-HQ'd buyer can mandate GCC-only deals;
    # `target_geography` above is the field that actually says so).
    org_hq_country: str | None = None
    org_sector_focus: list[str] = field(default_factory=list)
    org_description: str | None = None
    org_type: list[str] = field(default_factory=list)
    org_categories: list[str] = field(default_factory=list)
    org_region: str | None = None
