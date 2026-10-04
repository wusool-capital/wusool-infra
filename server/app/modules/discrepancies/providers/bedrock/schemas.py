"""Pydantic schema validating Bedrock's own raw JSON output — never an HTTP
DTO. Never trust raw LLM text past this boundary.
"""

from pydantic import BaseModel, Field

from app.modules.discrepancies.domain.criteria import ParsedContext
from app.modules.discrepancies.domain.vocabulary import REGION_OPTIONS, VERTICAL_OPTIONS

_VERTICALS = {v.casefold(): str(v) for v in VERTICAL_OPTIONS}
_REGIONS = {r.casefold(): r for r in REGION_OPTIONS}


def _canonical(value: str | None, options: dict[str, str]) -> str | None:
    return options.get(value.strip().casefold()) if value else None


# Plain `str`, not `Literal`: one off-list value must not fail the whole note.
class ExtractedContext(BaseModel):
    verticals: list[str] = Field(default_factory=list)
    region: str | None = None
    ticket_low_usd: float | None = None
    ticket_high_usd: float | None = None
    ebitda_low_usd: float | None = None
    ebitda_high_usd: float | None = None

    def to_domain(self) -> ParsedContext:
        return ParsedContext(
            verticals=tuple(
                dict.fromkeys(v for v in (_canonical(c, _VERTICALS) for c in self.verticals) if v)
            ),
            region=_canonical(self.region, _REGIONS),
            ticket_low=self.ticket_low_usd,
            ticket_high=self.ticket_high_usd,
            ebitda_low=self.ebitda_low_usd,
            ebitda_high=self.ebitda_high_usd,
        )
