"""
app/modules/meetings/domain/summary.py

Pure dataclass output of the summarization pipeline. No SQLAlchemy/
Pydantic/FastAPI imports — this is a domain object.

The field set is tuned to a sell-side M&A advisor's reading order rather
than to a generic meeting recap — see app.modules.meetings.domain.prompts
for the full rationale and the exact instructions behind each field.

`executive_summary` is the anchor field: besides being read by a human,
it's the field future pipelines (search, CRM sync, deal scoring, ...)
will consume, so it's produced in structured detail rather than a
one-line gist.

`notes` is the one nested field — a list of {"topic": str, "points":
list[str]} — because a flat list of topic labels (what `discussion_topics`
used to be) carried almost no information beyond `keywords`. The points
under a topic are the content.

`claims_to_verify` encodes the firm's "no document, no add-back" rule:
figures a party asserted out loud but hasn't evidenced yet. Keeping them
separate from `risks` turns each summary into the data-room document
request list.

`deal_momentum` is a single string ("Advanced | Held | Stalled | At risk
— <reason>") rather than a nested object; it's the only non-extractive
field, so the prompt requires the reason to cite the moment in the
transcript that justifies it. It only applies when an external
counterparty role (buyer/seller/investor) is tagged on the meeting —
for an internal/general meeting, or a buyer/seller/investor meeting
whose transcript gave the model nothing to judge, `deal_momentum == ""`
is the normal, expected output, not a degraded one.

`title` carries the company-role context resolved by
SummarizeMeetingCommand from the meeting's company tags (app.companies;
buyer/seller are tagged via the `/scribe --buyer/--seller` flags, the
other roles via the desktop push flow), when present — not from the
transcript itself. Seller comes first, then buyer, then investor, when
more than one is tagged. Internal/general meetings never get a bracket
prefix, even if a company happens to be tagged on them.

`keywords` stays a list[str] in the domain type (easiest to consume
downstream); `keywords_line` renders it the way every major AI
notetaker (Fireflies, Otter) displays keywords — one comma-separated
line, not bullets — for the two presentation surfaces (Slack, any
future UI) that want it pre-joined.
"""

from __future__ import annotations

from dataclasses import dataclass, field

__all__ = ["MeetingSummary", "SummaryNote"]


@dataclass(frozen=True, slots=True)
class SummaryNote:
    topic: str
    points: list[str] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MeetingSummary:
    title: str
    executive_summary: str
    notes: list[SummaryNote] = field(default_factory=list)
    decisions: list[str] = field(default_factory=list)
    action_items: list[str] = field(default_factory=list)
    claims_to_verify: list[str] = field(default_factory=list)
    risks: list[str] = field(default_factory=list)
    deal_momentum: str = ""
    keywords: list[str] = field(default_factory=list)

    @property
    def keywords_line(self) -> str:
        """Keywords as a single comma-separated line (e.g. 'floor price,
        EBITDA, data room') — the standard AI-notetaker presentation, not
        one bullet per keyword.
        """
        return ", ".join(self.keywords)
