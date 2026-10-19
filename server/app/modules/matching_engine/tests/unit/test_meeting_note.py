"""Meeting-notes prompt-section rendering: budget selection and labeling.
No DB, no Bedrock — pure functions only.
"""

from datetime import UTC, datetime

from app.modules.matching_engine.domain.meetings import (
    MIDDLE_TRUNCATED_MARKER,
    MeetingNote,
    render_meeting_notes_section,
    select_notes_within_budget,
    truncate_summary,
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


def test_select_within_budget_keeps_all_when_fewer_notes_than_budget() -> None:
    notes = [_note(30, "a" * 100), _note(20, "b" * 100), _note(10, "c" * 100)]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=12000)

    assert selected == notes
    assert omitted == 0


def test_select_within_budget_single_note_longer_than_budget_still_returned() -> None:
    notes = [_note(10, "z" * 500)]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=100)

    assert selected == notes
    assert omitted == 0


def test_select_within_budget_oldest_longer_than_budget_drops_all_newer() -> None:
    notes = [_note(30, "a" * 50), _note(20, "b" * 50), _note(10, "c" * 500)]

    selected, omitted = select_notes_within_budget(notes, total_char_budget=100)

    assert [n.summary[0] for n in selected] == ["c"]
    assert omitted == 2


def test_truncate_summary_returns_short_text_unchanged() -> None:
    assert truncate_summary("short", 3000) == ("short", False)
    assert truncate_summary("x" * 3000, 3000) == ("x" * 3000, False)


def test_truncate_summary_keeps_head_and_tail_with_marker() -> None:
    text = "H" * 2500 + "M" * 2000 + "T" * 1500

    cut, truncated = truncate_summary(text, 3000)

    assert truncated is True
    assert cut == "H" * 2000 + MIDDLE_TRUNCATED_MARKER + "T" * 1000
    assert len(cut) == 3000 + len(MIDDLE_TRUNCATED_MARKER)


def test_render_is_identical_at_old_and_new_budgets_when_notes_fit_old_limits() -> None:
    notes = [_note(30, "a" * 590), _note(20, "b" * 400), _note(10, "c" * 300)]

    old = render_meeting_notes_section(notes, total_char_budget=4000, subject_name="Acme")
    new = render_meeting_notes_section(notes, total_char_budget=12000, subject_name="Acme")

    assert old == new
    assert all(truncate_summary(n.summary, 3000) == (n.summary, False) for n in notes)


def test_render_includes_more_notes_at_new_budget_and_keeps_oldest() -> None:
    notes = [_note(d, str(d) * 1500) for d in (28, 24, 20, 16, 12, 8)]

    old = render_meeting_notes_section(notes, total_char_budget=4000, subject_name="Acme")
    new = render_meeting_notes_section(notes, total_char_budget=12000, subject_name="Acme")

    assert "older meetings omitted" in old
    assert new.count("\n- [") > old.count("\n- [")
    assert "[2026-01-08]" in old
    assert "[2026-01-08]" in new


def test_truncate_summary_cuts_one_char_over_cap() -> None:
    text = "a" * 2999 + "z" * 2

    cut, truncated = truncate_summary(text, 3000)

    assert truncated is True
    assert cut.endswith("z")
    assert MIDDLE_TRUNCATED_MARKER in cut


def test_truncate_summary_tiny_cap_keeps_a_tail_character() -> None:
    cut, truncated = truncate_summary("abcdef", 1)

    assert truncated is True
    assert cut == MIDDLE_TRUNCATED_MARKER + "f"
