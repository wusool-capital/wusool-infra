"""Meeting-notes prompt-section rendering: budget selection and labeling.
No DB, no Bedrock — pure functions only.
"""

from datetime import UTC, datetime

from app.modules.matching_engine.domain.meetings import (
    MeetingNote,
    render_meeting_notes_section,
    select_notes_within_budget,
)


def _note(day: int, summary: str) -> MeetingNote:
    return MeetingNote(
        occurred_at=datetime(2026, 1, day, tzinfo=UTC), title=None, summary=summary, truncated=False
    )


def test_render_returns_empty_string_when_no_notes() -> None:
    assert render_meeting_notes_section([], total_char_budget=4000, subject_name="Acme") == ""


def test_render_includes_all_notes_when_under_budget() -> None:
    notes = [_note(20, "recent note"), _note(10, "older note")]

    section = render_meeting_notes_section(notes, total_char_budget=4000, subject_name="Acme")

    assert "recent note" in section
    assert "older note" in section
    assert "omitted" not in section
    assert "Acme" in section


def test_select_within_budget_always_keeps_oldest_note() -> None:
    # Budget only fits the oldest note plus one more, but there are 3 total.
    notes = [_note(30, "x" * 100), _note(20, "y" * 100), _note(10, "founding mandate note")]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=150)

    assert selected[-1].summary == "founding mandate note"
    assert omitted == 1


def test_select_within_budget_single_note_returned_as_is() -> None:
    notes = [_note(10, "only note")]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=1)

    assert selected == notes
    assert omitted == 0


def test_render_states_omission_count_explicitly() -> None:
    notes = [_note(30, "a" * 100), _note(20, "b" * 100), _note(10, "c" * 100)]

    section = render_meeting_notes_section(notes, total_char_budget=250, subject_name="Acme")

    assert "(1 older meetings omitted)" in section
