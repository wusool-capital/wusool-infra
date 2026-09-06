"""Pydantic schema validating Bedrock's own raw JSON tool-call output — never
an HTTP DTO. `MeetingSummarySchema` is the strict validation target for the
forced-tool-call `return_structured_output` response and the source of the
`inputSchema` passed to Bedrock via `model_json_schema()`. Never trust raw
LLM text past this boundary; never expose this Pydantic model outside
`providers/bedrock/` — `client.py` returns `model_dump()`, not the model
itself, matching the `SummarizerLLM` port's `JsonObject` contract.
"""

from pydantic import BaseModel


class SummaryNoteSchema(BaseModel):
    topic: str
    points: list[str]


class MeetingSummarySchema(BaseModel):
    title: str
    executive_summary: str
    notes: list[SummaryNoteSchema]
    decisions: list[str]
    action_items: list[str]
    claims_to_verify: list[str]
    risks: list[str]
    deal_momentum: str
    keywords: list[str]
