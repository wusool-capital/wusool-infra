"""Pydantic schema validating Bedrock's own raw JSON output — never an HTTP
DTO. Never trust raw LLM text past this boundary.

`confidence` stays the raw `high`/`medium`/`low` label here — this schema
only validates Bedrock's shape. The single confidence->score mapping lives
in `application/enrich.py`; only the domain `ExtractedField`s from
`to_domain()` cross the `ExtractionClient` Port.
"""

from pydantic import BaseModel, Field

from app.modules.enrichment.domain.proposals import ConfidenceLevel, ExtractedField


class ExtractedFieldValue(BaseModel):
    field_name: str
    value: str
    source_url: str
    confidence: ConfidenceLevel
    rationale: str


class ExtractedFields(BaseModel):
    """The LLM must never invent a field not in the requested set, and must
    never fabricate a value with no source — absent information is simply
    omitted, never guessed.
    """

    fields: list[ExtractedFieldValue] = Field(default_factory=list)

    def to_domain(self) -> tuple[ExtractedField, ...]:
        return tuple(
            ExtractedField(
                field_name=f.field_name,
                value=f.value,
                source_url=f.source_url,
                confidence=f.confidence,
                rationale=f.rationale,
            )
            for f in self.fields
        )
