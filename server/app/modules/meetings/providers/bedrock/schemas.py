"""Pydantic schemas for Bedrock's forced tool-call output — never HTTP DTOs.
They are the Pydantic AI agents' `output_type` in `client.py`, so they define
the tool schema Bedrock is forced to fill and validate what comes back.
Never expose them outside `providers/bedrock/`: `client.py` returns the
domain types (`to_domain`/`CorrectionSuggestion`) the ports promise.
"""

from pydantic import BaseModel, Field

from app.modules.meetings.domain.corrections import CorrectionCategory, CorrectionEdit
from app.modules.meetings.domain.summary import MeetingSummary, SummaryNote


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

    def to_domain(self) -> MeetingSummary:
        return MeetingSummary(
            title=self.title,
            executive_summary=self.executive_summary,
            notes=[SummaryNote(topic=note.topic, points=note.points) for note in self.notes],
            decisions=self.decisions,
            action_items=self.action_items,
            claims_to_verify=self.claims_to_verify,
            risks=self.risks,
            deal_momentum=self.deal_momentum,
            keywords=self.keywords,
        )


class CorrectionItemSchema(BaseModel):
    # The batch-local line number; the server maps it back to a segment id.
    line: int = Field(ge=1)
    suggested: str
    category: CorrectionCategory
    reason: str


class TranscriptCorrectionsSchema(BaseModel):
    suggestions: list[CorrectionItemSchema]

    def to_domain(self) -> list[CorrectionEdit]:
        return [
            CorrectionEdit(
                line=item.line,
                suggested=item.suggested,
                category=item.category,
                reason=item.reason,
            )
            for item in self.suggestions
        ]
