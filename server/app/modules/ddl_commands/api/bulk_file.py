"""Reads a bulk upload file (CSV or Excel) into rows keyed by field name.

Two kinds of failure, kept apart on purpose: `TemplateError` means the file
is not the template (wrong headers, unreadable, too big) and rejects it as a
whole; a `CellProblem` is one bad value in an otherwise good file.
"""

import csv
import io
import zipfile
from collections.abc import Iterator, Sequence
from dataclasses import dataclass

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from app.modules.ddl_commands.api.bulk_columns import (
    CellError,
    CellValue,
    Column,
    coerce_cell,
    columns_for,
    normalize_label,
)
from app.modules.ddl_commands.api.bulk_store import MAX_ROWS, UploadKind
from app.modules.ddl_commands.api.bulk_upload import UploadRow
from app.modules.ddl_commands.api.schemas import PrefillValue
from app.modules.notifications import sanitize_mrkdwn

MAX_FILE_BYTES = 5 * 1024 * 1024
_HEADER_LINE = 1
_EXTENSIONS = (".csv", ".xlsx")


class TemplateError(Exception):
    """The file is not the template. The message is safe to show."""


@dataclass(frozen=True)
class CellProblem:
    line: int  # spreadsheet line, header is line 1
    column: str
    message: str


@dataclass(frozen=True)
class ParsedUpload:
    rows: tuple[UploadRow, ...]
    lines: tuple[int, ...]  # spreadsheet line of each row
    problems: tuple[CellProblem, ...]


def parse_upload(kind: UploadKind, filename: str, content: bytes) -> ParsedUpload:
    if not filename.lower().endswith(_EXTENSIONS):
        raise TemplateError("only .csv and .xlsx files are supported")
    if len(content) > MAX_FILE_BYTES:
        raise TemplateError(f"the file is larger than {MAX_FILE_BYTES // (1024 * 1024)} MB")

    # One extra row past the cap is enough to know the file is too long.
    limit = _HEADER_LINE + MAX_ROWS + 1
    if filename.lower().endswith(".csv"):
        sheet = list(_csv_rows(content, limit))
    else:
        sheet = list(_xlsx_rows(content, limit))
    if not sheet:
        raise TemplateError("the file is empty")

    header_cells = sheet[0]
    columns = _match_columns(kind, header_cells)
    data = [(line, cells) for line, cells in enumerate(sheet[1:], start=_HEADER_LINE + 1)]
    data = [(line, cells) for line, cells in data if any(_present(c) for c in cells)]
    if not data:
        raise TemplateError("the file has no data rows")
    if len(data) > MAX_ROWS:
        raise TemplateError(f"the file has more than {MAX_ROWS} rows")

    rows: list[UploadRow] = []
    lines: list[int] = []
    problems: list[CellProblem] = []
    for line, cells in data:
        row: UploadRow = {}
        for index, column in columns:
            raw = cells[index] if index < len(cells) else None
            try:
                value = _cell(column, raw)
            except CellError as exc:
                problems.append(CellProblem(line, column.label, str(exc)))
                continue
            if value is not None:
                row[column.field] = value
        rows.append(row)
        lines.append(line)
    return ParsedUpload(tuple(rows), tuple(lines), tuple(problems))


def _cell(column: Column, raw: CellValue) -> PrefillValue | None:
    if column.spec is None:  # organization name or domain
        text = None if raw is None else str(raw).strip()
        return text or None
    return coerce_cell(column.spec, raw)


def _present(cell: CellValue) -> bool:
    return cell is not None and not (isinstance(cell, str) and not cell.strip())


def _match_columns(kind: UploadKind, header_cells: Sequence[CellValue]) -> list[tuple[int, Column]]:
    by_label = {normalize_label(c.label): c for c in columns_for(kind)}
    headers = [(i, "" if c is None else str(c).strip()) for i, c in enumerate(header_cells)]
    headers = [(i, h) for i, h in headers if h]  # trailing blank header cells are noise
    unknown = [h for _, h in headers if normalize_label(h) not in by_label]
    if unknown:
        shown = ", ".join(sanitize_mrkdwn(h)[:40] for h in unknown[:5])
        raise TemplateError(f"unknown columns: {shown}")
    matched = [(i, by_label[normalize_label(h)]) for i, h in headers]
    labels = [c.label for _, c in matched]
    repeated = sorted({label for label in labels if labels.count(label) > 1})
    if repeated:
        raise TemplateError(f"repeated columns: {', '.join(repeated)}")
    missing = [c.label for c in columns_for(kind) if c.required and c.label not in labels]
    if missing:
        raise TemplateError(f"missing required columns: {', '.join(missing)}")
    return matched


def _csv_rows(content: bytes, limit: int) -> Iterator[list[CellValue]]:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        raise TemplateError("the file is not UTF-8. Save it as CSV UTF-8") from None
    first_line = text.split("\n", 1)[0]
    # Excel in some locales writes `;` between cells instead of `,`.
    delimiter = ";" if first_line.count(";") > first_line.count(",") else ","
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    for number, cells in enumerate(reader, start=1):
        if number > limit:
            return
        yield list(cells)


def _xlsx_rows(content: bytes, limit: int) -> Iterator[list[CellValue]]:
    try:
        workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
    except (zipfile.BadZipFile, InvalidFileException, KeyError, ValueError, OSError):
        raise TemplateError("the file could not be read as an Excel workbook") from None
    try:
        for row in workbook.worksheets[0].iter_rows(max_row=limit):
            yield [_xlsx_value(cell.value, cell.number_format) for cell in row]
    finally:
        workbook.close()


def _xlsx_value(value: CellValue, number_format: str | None) -> CellValue:
    # Excel stores 35% as 0.35; the add forms take 35.
    if isinstance(value, float) and number_format and "%" in number_format:
        return round(value * 100, 10)
    return value
