"""Pydantic schema validating Bedrock's own raw JSON output — never an HTTP
DTO. Never trust raw LLM text past this boundary.
"""

from pydantic import BaseModel

from app.modules.discrepancies.domain.criteria import ParsedContext
from app.modules.discrepancies.domain.vocabulary import REGION_OPTIONS, VERTICAL_OPTIONS


# Plain `str`, not `Literal`: one off-list value must not fail the whole note.
class ExtractedContext(BaseModel):
    vertical: str | None = None
    region: str | None = None
    ticket_low_usd: float | None = None
    ticket_high_usd: float | None = None
    ebitda_usd: float | None = None

    def to_domain(self) -> ParsedContext:
        return ParsedContext(
            vertical=self.vertical if self.vertical in VERTICAL_OPTIONS else None,
            region=self.region if self.region in REGION_OPTIONS else None,
            ticket_low=self.ticket_low_usd,
            ticket_high=self.ticket_high_usd,
            ebitda=self.ebitda_usd,
        )
