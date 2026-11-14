"""What a person reads about a bulk upload."""

import csv
import io

from app.modules.ddl_commands.api.bulk_file import CellProblem
from app.modules.ddl_commands.api.bulk_report import (
    SHOWN_PROBLEMS,
    ProblemLine,
    combine_problems,
    errors_csv,
    finished_text,
    has_hidden_problems,
    rejection_text,
)
from app.modules.ddl_commands.api.bulk_store import CommitProgress, RowOutcome
from app.modules.ddl_commands.api.bulk_upload import ProblemKind, RowProblem


def problem(
    row: int,
    kind: ProblemKind,
    field: str | None = None,
    *,
    error_type: str | None = None,
    duplicate_of: int | None = None,
) -> RowProblem:
    # The message is deliberately useless: the report must not depend on its wording.
    return RowProblem(
        row=row,
        kind=kind,
        field=field,
        error_type=error_type,
        duplicate_of=duplicate_of,
        message="(reworded by a future change)",
    )


def test_row_problems_use_column_labels_and_spreadsheet_wording() -> None:
    row_problems = [
        problem(3, "required", "org_name"),
        problem(4, "required", "domain"),
        problem(5, "invalid", "description", error_type="string_too_long"),
        problem(6, "duplicate", duplicate_of=2),
    ]

    lines = combine_problems("buyer", [], row_problems)

    assert [p.text for p in lines] == [
        "Line 3, Organization name: is required",
        "Line 4, Domain: is required",
        "Line 5, Description: is not valid (string_too_long)",
        "Line 6: same company as line 2",
    ]


def test_a_cell_problem_replaces_the_row_problems_it_would_also_cause() -> None:
    cell = [CellProblem(line=4, column="Target vertical", message="not an allowed value")]
    rows = [
        problem(4, "required", "target_vertical"),  # caused by the cell above
        problem(7, "required", "org_name"),
    ]

    lines = combine_problems("buyer", cell, rows)

    assert [p.text for p in lines] == [
        "Line 4, Target vertical: not an allowed value",
        "Line 7, Organization name: is required",
    ]


def test_problems_are_listed_in_line_order() -> None:
    cell = [CellProblem(line=9, column="Notes", message="x")]
    rows = [problem(2, "required", "org_name")]

    assert [p.line for p in combine_problems("seller", cell, rows)] == [2, 9]


def test_the_message_counts_problems_and_rows() -> None:
    problems = [ProblemLine(2, "Domain", "is required"), ProblemLine(2, "Notes", "bad")]

    text = rejection_text(problems)

    assert text.startswith("*Nothing was added.* 2 problems in 1 row.")
    assert "• Line 2, Domain: is required" in text
    assert "more" not in text


def test_one_problem_is_singular() -> None:
    assert "1 problem in 1 row." in rejection_text([ProblemLine(2, "", "x")])


def test_only_the_first_twenty_problems_are_listed_with_a_count_of_the_rest() -> None:
    problems = [ProblemLine(n, "Domain", "is required") for n in range(2, 32)]

    text = rejection_text(problems)

    assert text.count("• ") == SHOWN_PROBLEMS
    assert "Line 21," in text and "Line 22," not in text
    assert text.endswith("_…and 10 more._")


def test_a_long_list_is_cut_to_fit_a_slack_text_block() -> None:
    problems = [
        ProblemLine(n, "Sector focus", "not an allowed value. " + "x" * 300) for n in range(2, 22)
    ]

    text = rejection_text(problems)

    assert len(text) < 3000
    assert "more._" in text


def test_slack_markup_in_a_problem_is_escaped() -> None:
    text = rejection_text([ProblemLine(2, "Notes", "<!channel> & more")])

    assert "<!channel>" not in text
    assert "&lt;!channel&gt;" in text


def test_the_full_problem_list_is_a_csv_a_spreadsheet_opens_correctly() -> None:
    problems = [
        ProblemLine(2, "Domain", "is required"),
        ProblemLine(5, "", "same company as line 2"),
    ]

    content = errors_csv(problems)

    assert content.startswith(b"\xef\xbb\xbf")
    rows = list(csv.reader(io.StringIO(content.decode("utf-8-sig"))))
    assert rows == [
        ["Line", "Column", "Problem"],
        ["2", "Domain", "is required"],
        ["5", "", "same company as line 2"],
    ]


def test_a_clean_finish_is_one_line() -> None:
    progress = CommitProgress(
        state="done",
        total=3,
        added=2,
        skipped=(RowOutcome(row=4, kind="skipped", reason="already in the CRM"),),
    )

    assert finished_text(progress) == (
        "*Bulk add finished.* Added 2, skipped 1 already in the CRM, failed 0."
    )


def test_failures_are_listed_by_line_with_a_hint_to_upload_again() -> None:
    failed = tuple(
        RowOutcome(row=n, kind="failed", reason="RuntimeError; already saved: nothing")
        for n in range(2, 15)
    )

    text = finished_text(CommitProgress(state="done", total=13, added=0, failed=failed))

    assert "failed 13." in text
    assert "• Line 2: RuntimeError; already saved: nothing" in text
    assert "Line 12," not in text and "Line 12:" not in text
    assert "_…and 3 more._" in text
    assert "rows already added are skipped" in text


def test_hidden_problems_mean_the_full_list_must_be_attached() -> None:
    few_short = [ProblemLine(n, "Domain", "is required") for n in range(2, 12)]
    many_short = [ProblemLine(n, "Domain", "is required") for n in range(2, 30)]
    few_long = [ProblemLine(n, "Sector focus", "bad. " + "x" * 300) for n in range(2, 17)]

    assert not has_hidden_problems(few_short)
    assert has_hidden_problems(many_short)  # over twenty
    assert has_hidden_problems(few_long)  # under twenty, but too long to fit


def test_an_organization_field_that_shares_a_name_is_reported_under_its_own_label() -> None:
    problems = [
        problem(3, "invalid", "org_relationship_status", error_type="string_too_long"),
        problem(4, "invalid", "relationship_status", error_type="string_too_long"),
    ]

    lines = combine_problems("seller", [], problems)

    assert [(p.line, p.column) for p in lines] == [
        (3, "Relationship status"),
        (4, "Seller relationship status"),
    ]


def test_a_value_that_is_not_allowed_uses_the_column_label() -> None:
    lines = combine_problems("buyer", [], [problem(2, "not_allowed", "model")])

    assert lines[0].text == "Line 2, Model: is not an allowed value"


def test_an_unknown_kind_of_problem_falls_back_to_the_backend_message() -> None:
    row_problem = RowProblem(
        row=3, kind="unknown_field", field="nonsense", message="unknown field 'nonsense'"
    )

    lines = combine_problems("buyer", [], [row_problem])

    assert lines[0].text == "Line 3: unknown field 'nonsense'"
