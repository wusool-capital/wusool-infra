"""Meeting-notes prompt-section rendering: budget selection and labeling.
No DB, no Bedrock — pure functions only.
"""

from datetime import UTC, datetime

from app.modules.matching_engine.domain.meetings import (
    MAX_NOTE_CHARS,
    OVERSIZED_NOTE_MARKER,
    MeetingNote,
    bound_summary,
    render_meeting_notes_section,
    select_notes_within_budget,
)


def _note(day: int, summary: str) -> MeetingNote:
    return MeetingNote(occurred_at=datetime(2026, 1, day, tzinfo=UTC), title=None, summary=summary)


def test_render_returns_empty_string_when_no_notes() -> None:
    assert render_meeting_notes_section([], total_char_budget=4000, subject_name="Acme") == ""


def test_render_includes_all_notes_when_under_budget() -> None:
    notes = [_note(20, "recent note"), _note(10, "older note")]

    section = render_meeting_notes_section(notes, total_char_budget=4000, subject_name="Acme")

    assert "recent note" in section
    assert "older note" in section
    assert "omitted" not in section
    assert "Acme" in section


def test_render_keeps_a_long_summary_whole() -> None:
    summary = (
        "Gist.\n\nNext steps:\n- a\n\nNotes\n\n"
        + "Topic:\n- "
        + "x" * 9000
        + "\n\nLast topic:\n- end"
    )

    section = render_meeting_notes_section(
        [_note(10, summary)], total_char_budget=24000, subject_name="Acme"
    )

    assert summary in section


def test_select_keeps_newest_and_oldest_even_over_budget() -> None:
    notes = [_note(30, "n" * 10000), _note(20, "m" * 100), _note(10, "o" * 10000)]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=12000)

    assert [n.summary[0] for n in selected] == ["n", "o"]
    assert omitted == 1


def test_select_fills_budget_with_the_next_most_recent_notes() -> None:
    notes = [_note(d, str(d % 10) * 100) for d in (29, 25, 21, 17, 13)]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=400)

    assert [n.occurred_at.day for n in selected] == [29, 25, 21, 13]
    assert omitted == 1


def test_select_returns_one_or_two_notes_as_is() -> None:
    one = [_note(10, "z" * 500)]
    two = [_note(20, "a" * 500), _note(10, "b" * 500)]

    assert select_notes_within_budget(one, total_char_budget=1) == (one, 0)
    assert select_notes_within_budget(two, total_char_budget=1) == (two, 0)


def test_select_keeps_all_when_they_fit() -> None:
    notes = [_note(30, "a" * 100), _note(20, "b" * 100), _note(10, "c" * 100)]

    assert select_notes_within_budget(notes, total_char_budget=24000) == (notes, 0)


def test_render_states_omission_count_explicitly() -> None:
    notes = [_note(30, "a" * 100), _note(20, "b" * 100), _note(10, "c" * 100)]

    section = render_meeting_notes_section(notes, total_char_budget=250, subject_name="Acme")

    assert "(1 older meetings omitted)" in section


def test_bound_summary_keeps_real_summaries_whole_and_cuts_outsized_notes() -> None:
    assert bound_summary("x" * 10_000) == "x" * 10_000
    cut = bound_summary("y" * (MAX_NOTE_CHARS + 50_000))
    assert cut == "y" * MAX_NOTE_CHARS + OVERSIZED_NOTE_MARKER
