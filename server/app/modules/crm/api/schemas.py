"""The Engine's wire shapes for buyer and seller roles. Field names are camelCase
on the wire, as the Engine's own types are, and snake_case here."""

from datetime import date
from typing import Annotated, Literal

from fastapi import Query
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator
from pydantic.alias_generators import to_camel

from app.modules.crm.domain.roles import (
    BuyerChanges,
    BuyerFilters,
    Detail,
    FieldGroup,
    FieldKind,
    NewBuyer,
    NewSeller,
    OpenToSelling,
    Range,
    SellerChanges,
    SellerFilters,
)

_MILLION = 1_000_000
MAX_PAGE_SIZE = 100

# Whole-dollar amounts: never negative, and NaN or Infinity (which JSON parsers accept) are refused.
Usd = Annotated[float | None, Field(ge=0, allow_inf_nan=False)]


_SIZE_ORDER = "check size from is above check size to"


def _in_order(low: float | None, high: float | None, message: str) -> None:
    if low is not None and high is not None and low > high:
        raise ValueError(message)


# A field's value on the wire: text, an option, an amount, a date, yes or no, or a checklist.
DetailScalar = str | float | bool | list[str] | None


class ApiModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, from_attributes=True, frozen=True
    )


class DetailView(ApiModel):
    key: str
    value: DetailScalar


class DetailInput(ApiModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="forbid"
    )

    key: str = Field(min_length=1)
    value: DetailScalar = None


class FieldDefView(ApiModel):
    """A field the form draws by `kind`: a select or checklist from `options`, an amount, a date."""

    key: str
    label: str
    kind: FieldKind
    options: list[str]
    group: FieldGroup


def _details(inputs: list[DetailInput]) -> tuple[Detail, ...]:
    return tuple(
        Detail(d.key, tuple(d.value) if isinstance(d.value, list) else d.value) for d in inputs
    )


class PersonView(ApiModel):
    id: str
    name: str
    org: str
    role: Literal["buyer", "target"]
    title: str | None = None
    email: str | None = None


class TeamMemberView(ApiModel):
    id: str
    name: str


class MeView(ApiModel):
    id: str
    name: str
    email: str


class BuyerRoleView(ApiModel):
    id: str
    name: str
    type: str | None
    hq: str | None
    website: str | None
    sectors: list[str]
    geographies: list[str]
    check_size_min_usd: float | None
    check_size_max_usd: float | None
    ebitda_floor_usd: float | None
    owner_id: str | None
    status: str | None
    contact_ids: list[str]
    notes: str | None
    etag: str
    # Filled by the single-role read only; lists leave it empty.
    details: list[DetailView] = Field(default_factory=list)


class SellerRoleView(ApiModel):
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
    contact_ids: list[str]
    etag: str
    # Sellers have no notes column yet.
    notes: str | None = None
    details: list[DetailView] = Field(default_factory=list)


class BuyerFilterOptionsView(ApiModel):
    """`regions` and `countries` list everything Attio allows, for the edit form."""

    sectors: list[str]
    geographies: list[str]
    statuses: list[str]
    regions: list[str]
    countries: list[str]
    hq_countries: list[str]
    fields: list[FieldDefView]


class SellerFilterOptionsView(ApiModel):
    """`sector_choices` and `hq_countries` list everything Attio allows, for the add form."""

    sectors: list[str]
    geographies: list[str]
    sector_choices: list[str]
    hq_countries: list[str]
    fields: list[FieldDefView]


class BuyerRolePage(ApiModel):
    """`matched` counts rows under the filters and search; `total` counts every live buyer.

    `matched`, `total` and `options` come with the first page; later pages hold rows only.
    """

    rows: list[BuyerRoleView]
    matched: int
    total: int
    next_cursor: str | None
    options: BuyerFilterOptionsView


class SellerRolePage(ApiModel):
    """Counts and options come with the first page, as for buyers."""

    rows: list[SellerRoleView]
    matched: int
    total: int
    next_cursor: str | None
    options: SellerFilterOptionsView


class BuyerCreate(ApiModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="forbid"
    )

    name: str = Field(min_length=1)
    website: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    hq: str | None = None
    status: str | None = None
    notes: str | None = None
    check_size_min_usd: Usd = None
    check_size_max_usd: Usd = None
    ebitda_floor_usd: Usd = None
    # Regions and countries together; the Toolkit sorts them into Attio's two fields.
    geographies: list[str] | None = None
    details: list[DetailInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_size_in_order(self) -> "BuyerCreate":
        _in_order(
            self.check_size_min_usd,
            self.check_size_max_usd,
            "check size from is above check size to",
        )
        return self

    def to_domain(self) -> NewBuyer:
        return NewBuyer(
            name=self.name.strip(),
            website=self.website.strip(),
            sector=self.sector,
            hq=self.hq,
            status=self.status,
            notes=self.notes,
            check_size_min_usd=self.check_size_min_usd,
            check_size_max_usd=self.check_size_max_usd,
            ebitda_floor_usd=self.ebitda_floor_usd,
            geographies=tuple(self.geographies or ()),
            details=_details(self.details),
        )


class _Update(ApiModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="forbid"
    )

    @model_validator(mode="after")
    def _something_was_sent(self) -> "_Update":
        if not self.model_fields_set:
            raise ValueError("send at least one field")
        return self


class BuyerUpdate(_Update):
    """Only the fields sent change. A value can be changed but not emptied; a null is refused."""

    status: str | None = None
    notes: str | None = None
    check_size_min_usd: Usd = None
    check_size_max_usd: Usd = None
    ebitda_floor_usd: Usd = None
    geographies: list[str] | None = None
    details: list[DetailInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _check_size_in_order(self) -> "BuyerUpdate":
        _in_order(
            self.check_size_min_usd,
            self.check_size_max_usd,
            "check size from is above check size to",
        )
        return self

    def to_domain(self) -> BuyerChanges:
        return BuyerChanges(
            sent=frozenset(self.model_fields_set),
            status=self.status,
            notes=self.notes,
            check_size_min_usd=self.check_size_min_usd,
            check_size_max_usd=self.check_size_max_usd,
            ebitda_floor_usd=self.ebitda_floor_usd,
            geographies=tuple(self.geographies or ()),
            details=_details(self.details),
        )


class SellerCreate(ApiModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, frozen=True, extra="forbid"
    )

    name: str = Field(min_length=1)
    website: str = Field(min_length=1)
    sector: str = Field(min_length=1)
    hq: str | None = None
    open_to_selling: OpenToSelling | None = None
    est_revenue_usd: Usd = None
    est_ebitda_usd: Usd = None
    re_engage_date: date | None = None
    details: list[DetailInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _ebitda_not_above_revenue(self) -> "SellerCreate":
        _in_order(self.est_ebitda_usd, self.est_revenue_usd, "EBITDA is above revenue")
        return self

    def to_domain(self) -> NewSeller:
        return NewSeller(
            name=self.name.strip(),
            website=self.website.strip(),
            sector=self.sector,
            hq=self.hq,
            open_to_selling=self.open_to_selling,
            est_revenue_usd=self.est_revenue_usd,
            est_ebitda_usd=self.est_ebitda_usd,
            re_engage_date=self.re_engage_date,
            details=_details(self.details),
        )


class SellerUpdate(_Update):
    est_revenue_usd: Usd = None
    est_ebitda_usd: Usd = None
    open_to_selling: OpenToSelling | None = None
    re_engage_date: date | None = None
    details: list[DetailInput] = Field(default_factory=list)

    @model_validator(mode="after")
    def _consistent(self) -> "SellerUpdate":
        _in_order(self.est_ebitda_usd, self.est_revenue_usd, "EBITDA is above revenue")
        if "open_to_selling" in self.model_fields_set and self.open_to_selling is None:
            raise ValueError("open to selling cannot be cleared")
        return self

    def to_domain(self) -> SellerChanges:
        return SellerChanges(
            sent=frozenset(self.model_fields_set),
            est_revenue_usd=self.est_revenue_usd,
            est_ebitda_usd=self.est_ebitda_usd,
            open_to_selling=self.open_to_selling,
            re_engage_date=self.re_engage_date,
            details=_details(self.details),
        )


def _list(value: str | None) -> tuple[str, ...]:
    """A comma-separated URL value, as the Engine writes it ("Dental,Veterinary")."""
    return tuple(item for item in (value or "").split(",") if item)


def parse_range(value: str | None) -> Range:
    """A range in $M as the Engine writes it: "10-40", "10-" or "-40"."""
    if not value:
        return Range()
    low, _, high = value.partition("-")
    try:
        return Range(
            min=float(low) * _MILLION if low else None,
            max=float(high) * _MILLION if high else None,
        )
    except ValueError as exc:
        raise ValueError(f'"{value}" is not a range in $M such as "10-40"') from exc


class _PageQuery(BaseModel):
    model_config = ConfigDict(populate_by_name=True, frozen=True)

    q: str = ""
    cursor: str | None = None
    limit: int = Field(default=MAX_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE)
    sector: str | None = None
    geography: str | None = None


class BuyerFilterQuery(_PageQuery):
    """The Buyers page's URL params, passed through unchanged."""

    check_size: str | None = Field(default=None, alias="checkSize")
    min_ebitda: str | None = Field(default=None, alias="minEbitda")

    @field_validator("check_size", "min_ebitda")
    @classmethod
    def _is_range(cls, value: str | None) -> str | None:
        parse_range(value)
        return value

    def to_domain(self) -> BuyerFilters:
        return BuyerFilters(
            sectors=_list(self.sector),
            geographies=_list(self.geography),
            check_size=parse_range(self.check_size),
            min_ebitda=parse_range(self.min_ebitda),
            text=self.q,
        )


class SellerFilterQuery(_PageQuery):
    """The Sellers page's URL params, passed through unchanged."""

    revenue: str | None = None
    ebitda: str | None = None
    open_to_selling: str | None = Field(default=None, alias="openToSelling")

    @field_validator("revenue", "ebitda")
    @classmethod
    def _is_range(cls, value: str | None) -> str | None:
        parse_range(value)
        return value

    @field_validator("open_to_selling")
    @classmethod
    def _is_label(cls, value: str | None) -> str | None:
        allowed = {"Unknown", "Interested", "Warm intro"}
        unknown = [item for item in _list(value) if item not in allowed]
        if unknown:
            raise ValueError(f"unknown open-to-selling value: {', '.join(unknown)}")
        return value

    def to_domain(self) -> SellerFilters:
        labels: tuple[OpenToSelling, ...] = tuple(
            label  # validated above
            for label in ("Unknown", "Interested", "Warm intro")
            if label in _list(self.open_to_selling)
        )
        return SellerFilters(
            sectors=_list(self.sector),
            geographies=_list(self.geography),
            revenue=parse_range(self.revenue),
            ebitda=parse_range(self.ebitda),
            open_to_selling=labels,
            text=self.q,
        )


BuyerQuery = Annotated[BuyerFilterQuery, Query()]
SellerQuery = Annotated[SellerFilterQuery, Query()]


class ProblemDetail(BaseModel):
    """RFC 9457 problem details; `code` is stable and meant for the Engine to branch on."""

    type: str = "about:blank"
    title: str
    status: int
    detail: str
    code: str
    errors: list[str] = Field(default_factory=list)
    # What a failed multi-step write already saved.
    landed: list[str] = Field(default_factory=list)
