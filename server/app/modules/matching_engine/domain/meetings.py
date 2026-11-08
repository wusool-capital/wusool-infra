"""Free-text meeting/call note attached to an organization, sourced from the
shared `meetings` table (Attio migration + in-house Scribe recorder). No
SQLAlchemy import here — see mappers.py for the ORM->domain boundary.
"""

import logging
from dataclasses import dataclass
from datetime import datetime

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class MeetingNote:
    occurred_at: datetime
    title: str | None
    summary: str


def select_notes_within_budget(
    notes: list[MeetingNote], total_char_budget: int
) -> tuple[list[MeetingNote], int]:
    """`notes` must already be ordered most-recent-first. Each note is used
    whole — a summary is gist, next steps, deal signal and notes by topic,
    and cutting it would drop topics. The most recent note (where the
    relationship stands now) and the oldest (the founding/mandate-defining
    meeting) are always kept, even over budget; the budget then fills with
    the next most recent notes that fit. Returns (selected notes, count of
    older notes omitted). Never raises.
    """
    if len(notes) <= 2:
        return list(notes), 0

    newest, middle, oldest = notes[0], notes[1:-1], notes[-1]
    remaining_budget = total_char_budget - len(newest.summary) - len(oldest.summary)

    selected = [newest]
    used = 0
    for note in middle:
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
        "meeting_notes_section subject=%s included=%d omitted=%d",
        subject_name,
        len(selected),
        omitted,
    )
    return "\n".join(lines)
