"""What a person reads about a bulk upload: the problems in a rejected file, and
the result of an accepted one. Spreadsheet lines and column labels, never the
internal field names, and never the contents of a cell.
"""

import csv
import io
import re
from collections.abc import Sequence
from dataclasses import dataclass

from app.modules.ddl_commands.api.bulk_columns import columns_for
from app.modules.ddl_commands.api.bulk_file import CellProblem
from app.modules.ddl_commands.api.bulk_store import CommitProgress, UploadKind
from app.modules.ddl_commands.api.bulk_upload import RowProblem
from app.modules.notifications import sanitize_mrkdwn

SHOWN_PROBLEMS = 20
_SHOWN_FAILURES = 10
# Slack allows 3,000 characters in one text block; leave room for the heading.
_MAX_LIST_CHARS = 2400

_REQUIRED = re.compile(r"^(\w+) is required")
_INVALID = re.compile(r"^invalid '([^']+)' \((\w+)\)$")
_DUPLICATE = re.compile(r"^duplicate of row (\d+)$")


@dataclass(frozen=True)
class ProblemLine:
    line: int
    column: str  # empty when the problem is about the row as a whole
    message: str

    @property
    def text(self) -> str:
        where = f"Line {self.line}, {self.column}" if self.column else f"Line {self.line}"
        return f"{where}: {self.message}"


def combine_problems(
    kind: UploadKind, cell_problems: Sequence[CellProblem], row_problems: Sequence[RowProblem]
) -> list[ProblemLine]:
    """A cell problem is the root cause for its row, so the row-level problems it
    would also trigger (a bad vertical makes the vertical look missing) are dropped."""
    labels = {c.field: c.label for c in columns_for(kind)}
    lines = [ProblemLine(p.line, p.column, p.message) for p in cell_problems]
    broken = {p.line for p in cell_problems}
    for problem in row_problems:
        if problem.row not in broken:
            lines.append(_row_problem(problem, labels))
    return sorted(lines, key=lambda p: p.line)


def _row_problem(problem: RowProblem, labels: dict[str, str]) -> ProblemLine:
    message = problem.message
    if match := _REQUIRED.match(message):
        label = labels.get(match.group(1), match.group(1))
        return ProblemLine(problem.row, label, "is required")
    if match := _INVALID.match(message):
        label = labels.get(match.group(1), match.group(1))
        return ProblemLine(problem.row, label, f"is not valid ({match.group(2)})")
    if match := _DUPLICATE.match(message):
        return ProblemLine(problem.row, "", f"same company as line {match.group(1)}")
    return ProblemLine(problem.row, "", message)


def _visible(problems: Sequence[ProblemLine]) -> list[str]:
    shown: list[str] = []
    used = 0
    for problem in problems[:SHOWN_PROBLEMS]:
        item = f"• {sanitize_mrkdwn(problem.text)}"
        if used + len(item) > _MAX_LIST_CHARS:
            break
        shown.append(item)
        used += len(item) + 1
    return shown


def has_hidden_problems(problems: Sequence[ProblemLine]) -> bool:
    """True when the message can't list every problem, so the full list must be attached."""
    return len(_visible(problems)) < len(problems)


def rejection_text(problems: Sequence[ProblemLine]) -> str:
    rows = len({p.line for p in problems})
    shown = _visible(problems)
    head = (
        f"*Nothing was added.* {len(problems)} problem{'s' if len(problems) != 1 else ''} "
        f"in {rows} row{'s' if rows != 1 else ''}. Fix the file and upload it again."
    )
    more = len(problems) - len(shown)
    tail = f"\n_…and {more} more._" if more > 0 else ""
    return head + "\n\n" + "\n".join(shown) + tail


def errors_csv(problems: Sequence[ProblemLine]) -> bytes:
    """Every problem, for a person to work through in a spreadsheet."""
    buffer = io.StringIO()
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(["Line", "Column", "Problem"])
    writer.writerows([p.line, p.column, p.message] for p in problems)
    return buffer.getvalue().encode("utf-8-sig")


def finished_text(progress: CommitProgress) -> str:
    head = (
        f"*Bulk add finished.* Added {progress.added}, "
        f"skipped {len(progress.skipped)} already in the CRM, "
        f"failed {len(progress.failed)}."
    )
    if not progress.failed:
        return head
    shown = [
        f"• Line {f.row}: {sanitize_mrkdwn(f.reason or 'failed')}"
        for f in progress.failed[:_SHOWN_FAILURES]
    ]
    more = len(progress.failed) - _SHOWN_FAILURES
    tail = f"\n_…and {more} more._" if more > 0 else ""
    note = "\nRows that failed can be uploaded again; rows already added are skipped."
    return head + "\n\n" + "\n".join(shown) + tail + note
