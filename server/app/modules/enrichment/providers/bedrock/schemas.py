"""Pydantic schema validating Bedrock's own raw JSON output — never an HTTP
DTO. Never trust raw LLM text past this boundary.

`confidence` stays the raw `high`/`medium`/`low` label here — this schema
only validates Bedrock's shape. The single confidence->score mapping lives
in `application/enrich.py`, since a `.model_dump()`'d schema (what actually
crosses the `ExtractionClient` Port) discards computed properties, so a
property here would be unreachable dead code.
"""

from typing import Literal

from pydantic import BaseModel, Field

ConfidenceLevel = Literal["high", "medium", "low"]


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
