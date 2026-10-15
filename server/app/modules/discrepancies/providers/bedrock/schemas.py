"""Pydantic schema validating Bedrock's own raw JSON output — never an HTTP
DTO. Never trust raw LLM text past this boundary.
"""

from pydantic import BaseModel, Field

from app.modules.discrepancies.domain.criteria import ParsedContext
from app.modules.discrepancies.domain.vocabulary import (
    COUNTRY_OPTIONS,
    REGION_OPTIONS,
    SELLER_STATUS_OPTIONS,
    VERTICAL_OPTIONS,
)

_VERTICALS = {v.casefold(): str(v) for v in VERTICAL_OPTIONS}
_REGIONS = {r.casefold(): r for r in REGION_OPTIONS}
_COUNTRIES = {c.casefold(): c for c in COUNTRY_OPTIONS}
_SELLER_STATUSES = {s.casefold(): s for s in SELLER_STATUS_OPTIONS}


def _canonical(value: str | None, options: dict[str, str]) -> str | None:
    return options.get(value.strip().casefold()) if value else None


def _canonical_all(values: list[str], options: dict[str, str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(v for v in (_canonical(c, options) for c in values) if v))


def _bounds(low: float | None, high: float | None) -> tuple[float | None, float | None]:
    # A non-positive amount is never a real limit; reversed bounds are a model slip.
    low = low if low is not None and low > 0 else None
    high = high if high is not None and high > 0 else None
    if low is not None and high is not None and low > high:
        return high, low
    return low, high


# Plain `str`, not `Literal`: one off-list value must not fail the whole note.
class ExtractedContext(BaseModel):
    verticals: list[str] = Field(default_factory=list)
    region: str | None = None
    countries: list[str] = Field(default_factory=list)
    ticket_low_usd: float | None = None
    ticket_high_usd: float | None = None
    ebitda_low_usd: float | None = None
    ebitda_high_usd: float | None = None
    modifier_verticals: list[str] = Field(default_factory=list)
    excluded_verticals: list[str] = Field(default_factory=list)
    ev_ceiling_usd: float | None = None
    revenue_low_usd: float | None = None
    revenue_high_usd: float | None = None
    seller_status: list[str] = Field(default_factory=list)

    def to_domain(self) -> ParsedContext:
        ticket_low, ticket_high = _bounds(self.ticket_low_usd, self.ticket_high_usd)
        ebitda_low, ebitda_high = _bounds(self.ebitda_low_usd, self.ebitda_high_usd)
        revenue_low, revenue_high = _bounds(self.revenue_low_usd, self.revenue_high_usd)
        _, ev_ceiling = _bounds(None, self.ev_ceiling_usd)
        return ParsedContext(
            verticals=tuple(
                dict.fromkeys(v for v in (_canonical(c, _VERTICALS) for c in self.verticals) if v)
            ),
            region=_canonical(self.region, _REGIONS),
            countries=tuple(
                dict.fromkeys(c for c in (_canonical(n, _COUNTRIES) for n in self.countries) if c)
            ),
            ticket_low=ticket_low,
            ticket_high=ticket_high,
            ebitda_low=ebitda_low,
            ebitda_high=ebitda_high,
            modifier_verticals=_canonical_all(self.modifier_verticals, _VERTICALS),
            excluded_verticals=_canonical_all(self.excluded_verticals, _VERTICALS),
            ev_ceiling=ev_ceiling,
            revenue_low=revenue_low,
            revenue_high=revenue_high,
            seller_status=_canonical_all(self.seller_status, _SELLER_STATUSES),
        )
