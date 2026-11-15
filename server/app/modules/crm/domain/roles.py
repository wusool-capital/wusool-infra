"""Buyer and seller roles as the Engine reads them, plus the filters and edits it sends.

Fields with no clean source today are `None` (the Engine shows "—"); they move to
real columns when the Phase 0 tables land.
"""

from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date
from typing import Literal

RoleKind = Literal["buyer", "seller"]
OpenToSelling = Literal["Unknown", "Interested", "Warm intro"]

# The appetite signals Attio holds, grouped under the Engine's three labels.
_APPETITE_BY_LABEL: dict[OpenToSelling, tuple[str, ...]] = {
    "Unknown": ("No Signal",),
    "Interested": (
        "Expressed Interest Directly / Inbound Deal",
        "Listed on Business-for-Sale Platform",
    ),
    "Warm intro": ("Warm Introduction / Direct Outreach",),
}


def open_to_selling(appetite_signal: str | None) -> OpenToSelling:
    for label, signals in _APPETITE_BY_LABEL.items():
        if appetite_signal in signals:
            return label
    return "Unknown"


def appetite_signals(label: OpenToSelling) -> tuple[str, ...]:
    return _APPETITE_BY_LABEL[label]


@dataclass(frozen=True)
class Person:
    id: str
    name: str
    org: str
    role: Literal["buyer", "target"]
    title: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class TeamMember:
    id: str
    name: str


@dataclass(frozen=True)
class BuyerRole:
    id: str
    name: str
    hq: str | None
    website: str | None
    sectors: tuple[str, ...]
    geographies: tuple[str, ...]
    check_size_min_usd: float | None
    check_size_max_usd: float | None
    ebitda_floor_usd: float | None
    owner_id: str | None
    status: str | None
    contact_ids: tuple[str, ...]
    notes: str | None
    etag: str
    # No source column yet.
    type: None = None


@dataclass(frozen=True)
class SellerRole:
    id: str
    name: str
    hq: str | None
    website: str | None
    sector: str | None
    geography: str | None
    est_revenue_usd: float | None
    est_ebitda_usd: float | None
    open_to_selling: OpenToSelling
    re_engage_date: date | None
    owner_id: str | None
    contact_ids: tuple[str, ...]
    etag: str


@dataclass(frozen=True)
class Range:
    """In USD. A missing side is open."""

    min: float | None = None
    max: float | None = None

    @property
    def is_open(self) -> bool:
        return self.min is None and self.max is None


@dataclass(frozen=True)
class BuyerFilters:
    sectors: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    check_size: Range = field(default_factory=Range)
    min_ebitda: Range = field(default_factory=Range)
    text: str = ""

    @property
    def narrows(self) -> bool:
        """True when a filter other than the text search is set."""
        return bool(
            self.sectors
            or self.geographies
            or not self.check_size.is_open
            or not self.min_ebitda.is_open
        )


@dataclass(frozen=True)
class SellerFilters:
    sectors: tuple[str, ...] = ()
    geographies: tuple[str, ...] = ()
    revenue: Range = field(default_factory=Range)
    ebitda: Range = field(default_factory=Range)
    open_to_selling: tuple[OpenToSelling, ...] = ()
    text: str = ""


@dataclass(frozen=True)
class BuyerFilterOptions:
    sectors: tuple[str, ...]
    geographies: tuple[str, ...]
    statuses: tuple[str, ...]
    # Everything Attio allows, for the edit form; the service adds these.
    regions: tuple[str, ...] = ()
    countries: tuple[str, ...] = ()
    hq_countries: tuple[str, ...] = ()


@dataclass(frozen=True)
class SellerFilterOptions:
    sectors: tuple[str, ...]
    geographies: tuple[str, ...]
    # Everything Attio allows, for the add form; the service adds these.
    sector_choices: tuple[str, ...] = ()
    hq_countries: tuple[str, ...] = ()


@dataclass(frozen=True)
class BuyersPage:
    rows: tuple[BuyerRole, ...]
    people: tuple[Person, ...]
    users: tuple[TeamMember, ...]
    matched: int
    total: int
    next_cursor: str | None
    options: BuyerFilterOptions


@dataclass(frozen=True)
class SellersPage:
    rows: tuple[SellerRole, ...]
    people: tuple[Person, ...]
    users: tuple[TeamMember, ...]
    matched: int
    total: int
    next_cursor: str | None
    options: SellerFilterOptions


@dataclass(frozen=True)
class NewBuyer:
    name: str
    website: str
    sector: str
    hq: str | None = None
    status: str | None = None
    notes: str | None = None
    check_size_min_usd: float | None = None
    check_size_max_usd: float | None = None
    ebitda_floor_usd: float | None = None
    geographies: tuple[str, ...] = ()


@dataclass(frozen=True)
class NewSeller:
    name: str
    website: str
    sector: str
    hq: str | None = None
    open_to_selling: OpenToSelling | None = None
    est_revenue_usd: float | None = None
    est_ebitda_usd: float | None = None
    re_engage_date: date | None = None


@dataclass(frozen=True)
class BuyerChanges:
    """Only the fields the caller sent; `None` there means "clear the value"."""

    sent: frozenset[str]
    status: str | None = None
    notes: str | None = None
    geographies: tuple[str, ...] = ()
    check_size_min_usd: float | None = None
    check_size_max_usd: float | None = None
    ebitda_floor_usd: float | None = None


@dataclass(frozen=True)
class SellerChanges:
    sent: frozenset[str]
    est_revenue_usd: float | None = None
    est_ebitda_usd: float | None = None
    open_to_selling: OpenToSelling | None = None
    re_engage_date: date | None = None


@dataclass(frozen=True)
class GeographySplit:
    regions: tuple[str, ...]
    countries: tuple[str, ...]
    unknown: tuple[str, ...]


def split_geographies(
    picked: Sequence[str], regions: Sequence[str], countries: Sequence[str]
) -> GeographySplit:
    """Attio keeps a buyer's geography as two fields. The two lists never share a value."""
    return GeographySplit(
        regions=tuple(g for g in picked if g in regions),
        countries=tuple(g for g in picked if g in countries),
        unknown=tuple(g for g in picked if g not in regions and g not in countries),
    )


@dataclass(frozen=True)
class SignedInUser:
    id: str
    name: str
    email: str


class RoleNotFoundError(Exception):
    """No live role has this id."""


class StaleRoleError(Exception):
    """The caller edited a version that has since changed."""


class RoleAlreadyExistsError(Exception):
    """The company already holds this role."""

    def __init__(self, role_id: str, kind: RoleKind = "buyer") -> None:
        super().__init__(f"{kind} role {role_id} already exists")
        self.role_id = role_id
        self.kind = kind


class InvalidRoleFieldsError(Exception):
    """A field was refused; `problems` holds one readable line per field."""

    def __init__(self, problems: tuple[str, ...]) -> None:
        super().__init__("; ".join(problems))
        self.problems = problems


class WriteLandedPartlyError(Exception):
    """Attio changed but Postgres did not (or the reverse): `landed` names what saved."""

    def __init__(self, landed: tuple[str, ...], message: str) -> None:
        super().__init__(message)
        self.landed = landed


class InvalidCursorError(Exception):
    """The paging cursor was not issued by this API."""
