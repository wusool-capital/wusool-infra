"""Value objects for a buyer's stored criteria and a discrepancy report.
No database session or SQLAlchemy import here — `BuyerCriteria` is what the
`BuyerCriteriaReaderPort` hands back, mapped from `matching_engine`'s own
`BuyerContext` on the other side of that Port.
"""

from dataclasses import dataclass, field
from typing import Literal

from app.modules.discrepancies.domain.vocabulary import Criterion

DiscrepancyKind = Literal["conflict", "missing"]


@dataclass(frozen=True)
class BuyerCriteria:
    buyer_role_id: str
    org_name: str
    target_vertical: str | None
    # Disambiguates two orgs that would otherwise render identically in the
    # `/check-buyer` picker (same name, same/no vertical) — not used by any
    # rule, display only.
    org_hq_country: str | None = None
    target_region: list[str] = field(default_factory=list)
    target_country: list[str] = field(default_factory=list)
    check_size_min: float | None = None
    check_size_max: float | None = None
    ebitda_floor: float | None = None
    ebitda_ceiling: float | None = None


@dataclass(frozen=True)
class ParsedContext:
    """What the advisor asked for in their note; amounts are absolute USD.
    A single bound set means open-ended ("at least" / "up to"). `verticals`
    holds every option the note could mean (most likely first), since options
    overlap."""

    verticals: tuple[str, ...] = ()
    region: str | None = None
    ticket_low: float | None = None
    ticket_high: float | None = None
    ebitda_low: float | None = None
    ebitda_high: float | None = None


@dataclass(frozen=True)
class Discrepancy:
    criterion: Criterion
    kind: DiscrepancyKind
    stored: str
    stated: str | None = None


@dataclass(frozen=True)
class DiscrepancyReport:
    buyer_role_id: str
    conflicts: tuple[Discrepancy, ...] = ()
    missing: tuple[Discrepancy, ...] = ()

    @property
    def has_conflicts(self) -> bool:
        return len(self.conflicts) > 0

    @property
    def has_missing(self) -> bool:
        return len(self.missing) > 0

    @property
    def is_clear(self) -> bool:
        return not self.has_conflicts and not self.has_missing
