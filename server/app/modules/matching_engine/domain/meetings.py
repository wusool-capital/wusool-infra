"""Free-text meeting/call note attached to an organization, sourced from the
shared `meetings` table (Attio migration + in-house Scribe recorder). No
SQLAlchemy import here — see mappers.py for the ORM->domain boundary.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)

# Marks the cut so the model doesn't read a shortened summary as complete.
MIDDLE_TRUNCATED_MARKER = " ... [middle truncated] ... "


@dataclass(frozen=True)
class MeetingNote:
    occurred_at: datetime
    title: str | None
    summary: str
    truncated: bool


def truncate_summary(summary: str, max_chars: int) -> tuple[str, bool]:
    """Returns (text, was_truncated). Over-cap summaries keep their start
    (context) and end (next steps, terms) — the middle is what gets cut.
    """
    if len(summary) <= max_chars:
        return summary, False
    head_chars = max_chars * 2 // 3
    tail_chars = max_chars - head_chars
    tail = summary[-tail_chars:] if tail_chars else ""
    return f"{summary[:head_chars]}{MIDDLE_TRUNCATED_MARKER}{tail}", True


def select_notes_within_budget(
    notes: list[MeetingNote], total_char_budget: int
) -> tuple[list[MeetingNote], int]:
    """`notes` must already be ordered most-recent-first. Fills
    `total_char_budget` greedily from most recent, but always keeps the
    oldest note too — a buyer's founding/mandate-defining meeting shouldn't
    silently drop just because more recent, narrower ones exist. Returns
    (selected notes, count of older notes omitted). Never raises.
    """
    if len(notes) <= 1:
        return list(notes), 0

    oldest = notes[-1]
    remaining_budget = total_char_budget - len(oldest.summary)

    selected: list[MeetingNote] = []
    used = 0
    for note in notes[:-1]:
        cost = len(note.summary)
        if used + cost > remaining_budget:
            break
        selected.append(note)
        used += cost

    omitted = len(notes) - len(selected) - 1
    return [*selected, oldest], omitted


def render_meeting_notes_section(
    notes: list[MeetingNote], *, total_char_budget: int, subject_name: str
) -> str:
    """Renders the labeled, budget-capped meeting-notes block used in both
    the extraction and reasoning prompts. Returns "" when `notes` is empty —
    callers must omit the section entirely rather than render an empty
    header, so prompts stay byte-identical to the no-notes case.
    """
    if not notes:
        return ""

    selected, omitted = select_notes_within_budget(notes, total_char_budget)
    lines = [
        "Recent meeting notes (context only, not verified CRM data — may "
        "also describe other organizations mentioned in conversation, not "
        f"only {subject_name}; never treat facts here as confirmed unless "
        "they also appear in the structured fields above):"
    ]
    lines.extend(f"- [{note.occurred_at.date().isoformat()}] {note.summary}" for note in selected)
    if omitted:
        lines.append(f"({omitted} older meetings omitted)")
    logger.debug(
        "meeting_notes_section subject=%s included=%d truncated=%d omitted=%d",
        subject_name,
        len(selected),
        sum(note.truncated for note in selected),
        omitted,
    )
    return "\n".join(lines)
