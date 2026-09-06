"""
app/modules/meetings/domain/rendering.py

Flattens a structured MeetingSummary into the plain-text `summary` column
and reconstructs "Speaker: text" transcript lines from typed transcript
turns. Ported from `_render_summary_text`/`_render_transcript_text` in
Scribe's `app/publish/service.py`.

matching_engine's prompts read this exact rendered text, and
domain.chunking's paragraph splitter depends on the blank-line separator
between sections/turns — do not change either without checking both
consumers.

Scribe's originals worked off raw JSON dicts and so needed dict/list
coercion helpers (`_text_field`, `_text_list_field`) to degrade a
malformed LLM response instead of raising. Here the input is already a
validated `MeetingSummary`/`TranscriptTurn`, so those helpers aren't
needed — the type system is the validation.
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.meetings.domain.summary import MeetingSummary

__all__ = ["TranscriptTurn", "render_summary_text", "render_transcript_text"]

# Transcript turns are joined with a blank line rather than a single
# newline, matching how SummarizeMeetingCommand reconstructs the transcript
# (app/meetings/service/commands.py) so both paths render identically.
_TURN_SEPARATOR = "\n\n"


@dataclass(frozen=True, slots=True)
class TranscriptTurn:
    speaker: str
    text: str


def render_summary_text(summary: MeetingSummary) -> str:
    """Flatten the structured summary into the plain-text `summary` column.

    Wusool's schema stores one text summary, but the AI produces several
    sections; dropping everything but the executive summary would lose the
    action items and decisions, which are the parts a deal pipeline
    actually acts on. Sections that came back empty are omitted entirely
    rather than rendered as empty headings.
    """
    parts: list[str] = []

    if summary.executive_summary:
        parts.append(summary.executive_summary)

    for values, heading in (
        (summary.decisions, "Decisions"),
        (summary.action_items, "Action Items"),
        (summary.risks, "Risks"),
        (summary.claims_to_verify, "Claims to Verify"),
    ):
        if values:
            bullets = "\n".join(f"- {value}" for value in values)
            parts.append(f"{heading}:\n{bullets}")

    if summary.deal_momentum:
        parts.append(f"Deal Momentum: {summary.deal_momentum}")

    if summary.keywords:
        parts.append(f"Keywords: {summary.keywords_line}")

    return "\n\n".join(parts)


def render_transcript_text(turns: list[TranscriptTurn]) -> str:
    """Reconstruct 'Speaker: text' turns from a diarized transcript."""
    return _TURN_SEPARATOR.join(f"{turn.speaker}: {turn.text}" for turn in turns)
