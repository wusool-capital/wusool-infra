"""Reading a bulk upload file: CSV and Excel, line numbers, and the two kinds of failure."""

import csv
import io
from collections.abc import Sequence
from datetime import date

import pytest
from openpyxl import Workbook

import app.modules.ddl_commands.api.bulk_file as bulk_file
from app.modules.ddl_commands.api.bulk_columns import CellValue, columns_for
from app.modules.ddl_commands.api.bulk_file import TemplateError, parse_upload
from app.modules.ddl_commands.api.bulk_store import MAX_ROWS, UploadKind
from app.modules.ddl_commands.api.buyers import BUYER_ROLE_FIELDS_BY_NAME

VERTICAL = BUYER_ROLE_FIELDS_BY_NAME["target_vertical"].options[0]


def label(kind: UploadKind, field: str) -> str:
    return next(c.label for c in columns_for(kind) if c.field == field)


BUYER_HEADER = [label("buyer", f) for f in ("org_name", "domain", "target_vertical")]


def csv_bytes(
    header: list[str], rows: list[list[str]], *, delimiter: str = ",", bom: bool = True
) -> bytes:
    buffer = io.StringIO()
    writer = csv.writer(buffer, delimiter=delimiter, lineterminator="\r\n")
    writer.writerow(header)
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig" if bom else "utf-8")


def xlsx_bytes(
    rows: Sequence[Sequence[CellValue]], *, formats: dict[str, str] | None = None
) -> bytes:
    workbook = Workbook()
    sheet = workbook.active
    assert sheet is not None
    for row in rows:
        sheet.append(row)
    for cell, number_format in (formats or {}).items():
        sheet[cell].number_format = number_format
    buffer = io.BytesIO()
    workbook.save(buffer)
    return buffer.getvalue()


def test_a_csv_becomes_rows_keyed_by_field_name_with_spreadsheet_lines() -> None:
    header = [*BUYER_HEADER, label("buyer", "ebitda_floor"), label("buyer", "earnout_tolerance")]
    content = csv_bytes(
        header,
        [
            ["Acme", "https://www.acme.com", VERTICAL, "$1,500,000", "Yes"],
            ["Beta", "b.com", VERTICAL.lower(), "", "no"],
        ],
    )

    parsed = parse_upload("buyer", "list.csv", content)

    assert parsed.lines == (2, 3)
    assert parsed.problems == ()
    assert parsed.rows[0] == {
        "org_name": "Acme",
        "domain": "https://www.acme.com",
        "target_vertical": VERTICAL,
        "ebitda_floor": 1500000.0,
        "earnout_tolerance": True,
    }
    assert parsed.rows[1] == {
        "org_name": "Beta",
        "domain": "b.com",
        "target_vertical": VERTICAL,
        "earnout_tolerance": False,
    }


def test_arabic_text_survives_a_utf8_csv() -> None:
    content = csv_bytes(BUYER_HEADER, [["شركة الاختبار", "test.sa", VERTICAL]])

    assert parse_upload("buyer", "list.csv", content).rows[0]["org_name"] == "شركة الاختبار"


def test_a_semicolon_csv_from_an_excel_locale_is_read() -> None:
    content = csv_bytes(BUYER_HEADER, [["Acme", "acme.com", VERTICAL]], delimiter=";")

    assert parse_upload("buyer", "list.csv", content).rows[0]["domain"] == "acme.com"


def test_header_matching_ignores_case_and_extra_spaces() -> None:
    header = ["  ORGANIZATION   name ", "domain", "target VERTICAL"]

    parsed = parse_upload("buyer", "list.csv", csv_bytes(header, [["Acme", "acme.com", VERTICAL]]))

    assert set(parsed.rows[0]) == {"org_name", "domain", "target_vertical"}


def test_blank_rows_are_skipped_but_lines_keep_counting() -> None:
    content = csv_bytes(
        BUYER_HEADER,
        [["Acme", "a.com", VERTICAL], ["", "", ""], ["Beta", "b.com", VERTICAL], ["", "", ""]],
    )

    parsed = parse_upload("buyer", "list.csv", content)

    assert parsed.lines == (2, 4)
    assert [r["org_name"] for r in parsed.rows] == ["Acme", "Beta"]


def test_a_bad_cell_is_reported_with_its_line_and_column_and_the_rest_is_kept() -> None:
    floor = label("buyer", "ebitda_floor")
    content = csv_bytes(
        [*BUYER_HEADER, floor],
        [["Acme", "a.com", VERTICAL, "lots"], ["Beta", "b.com", "Not a vertical", "5"]],
    )

    parsed = parse_upload("buyer", "list.csv", content)

    assert [(p.line, p.column) for p in parsed.problems] == [(2, floor), (3, "Target vertical")]
    assert parsed.problems[0].message == "must be an amount"
    assert "ebitda_floor" not in parsed.rows[0]
    assert parsed.rows[1]["ebitda_floor"] == 5.0


def test_excel_cells_keep_their_types() -> None:
    header = [*BUYER_HEADER, label("buyer", "ebitda_floor"), label("buyer", "earnout_tolerance")]
    header += [label("buyer", "last_mandate_briefing_date")]
    content = xlsx_bytes([header, ["Acme", "a.com", VERTICAL, 2500000, True, date(2026, 3, 31)]])

    parsed = parse_upload("buyer", "list.xlsx", content)

    assert parsed.problems == ()
    assert parsed.rows[0]["ebitda_floor"] == 2500000.0
    assert parsed.rows[0]["earnout_tolerance"] is True
    assert parsed.rows[0]["last_mandate_briefing_date"] == date(2026, 3, 31)


def test_an_excel_percent_cell_is_read_as_the_number_shown() -> None:
    header = [label("seller", f) for f in ("org_name", "domain", "gross_margin_pct")]
    content = xlsx_bytes([header, ["Acme", "a.com", 0.35]], formats={"C2": "0%"})

    assert parse_upload("seller", "list.xlsx", content).rows[0]["gross_margin_pct"] == 35.0


def test_only_the_first_excel_sheet_is_read() -> None:
    workbook = Workbook()
    first = workbook.active
    assert first is not None
    first.append(BUYER_HEADER)
    first.append(["Acme", "a.com", VERTICAL])
    workbook.create_sheet("Notes").append(["not", "a", "table"])
    buffer = io.BytesIO()
    workbook.save(buffer)

    parsed = parse_upload("buyer", "list.xlsx", buffer.getvalue())

    assert [r["org_name"] for r in parsed.rows] == ["Acme"]


def test_a_file_of_exactly_the_row_limit_is_accepted() -> None:
    rows = [[f"Co {n}", f"co{n}.com", VERTICAL] for n in range(MAX_ROWS)]

    parsed = parse_upload("buyer", "list.csv", csv_bytes(BUYER_HEADER, rows))

    assert len(parsed.rows) == MAX_ROWS
    assert parsed.lines[-1] == MAX_ROWS + 1


@pytest.mark.parametrize(
    ("filename", "content", "reason"),
    [
        ("list.txt", b"x", "only .csv and .xlsx files are supported"),
        ("list.csv", b"", "the file is empty"),
        ("list.csv", csv_bytes(BUYER_HEADER, []), "the file has no data rows"),
        ("list.csv", b"\xff\xfe\x00bad", "the file is not UTF-8. Save it as CSV UTF-8"),
        ("list.xlsx", b"not a zip file", "the file could not be read as an Excel workbook"),
        (
            "list.csv",
            csv_bytes([*BUYER_HEADER, "Foo", "Bar"], [["A", "a.com", VERTICAL, "", ""]]),
            "unknown columns: Foo, Bar",
        ),
        (
            "list.csv",
            csv_bytes(["Organization name", "Target vertical"], [["A", VERTICAL]]),
            "missing required columns: Domain",
        ),
        (
            "list.csv",
            csv_bytes([*BUYER_HEADER, "Domain"], [["A", "a.com", VERTICAL, "b.com"]]),
            "repeated columns: Domain",
        ),
        (
            "list.csv",
            csv_bytes(
                BUYER_HEADER, [[f"Co {n}", f"co{n}.com", VERTICAL] for n in range(MAX_ROWS + 1)]
            ),
            f"the file has more than {MAX_ROWS} rows",
        ),
    ],
)
def test_a_file_that_is_not_the_template_is_rejected_whole(
    filename: str, content: bytes, reason: str
) -> None:
    with pytest.raises(TemplateError) as raised:
        parse_upload("buyer", filename, content)

    assert str(raised.value) == reason


def test_a_missing_buyer_vertical_column_is_named() -> None:
    content = csv_bytes(["Organization name", "Domain"], [["A", "a.com"]])

    with pytest.raises(TemplateError, match="Target vertical"):
        parse_upload("buyer", "list.csv", content)
    # A seller file needs no vertical.
    assert parse_upload("seller", "list.csv", content).rows[0]["domain"] == "a.com"


def test_unknown_column_names_are_shortened_and_made_safe_for_slack() -> None:
    header = [*BUYER_HEADER, "<!channel> " + "x" * 80]
    content = csv_bytes(header, [["A", "a.com", VERTICAL, ""]])

    with pytest.raises(TemplateError) as raised:
        parse_upload("buyer", "list.csv", content)

    message = str(raised.value)
    assert "<!channel>" not in message
    assert "&lt;!channel&gt;" in message
    assert len(message) < 120


def test_only_the_first_five_unknown_columns_are_listed() -> None:
    header = [*BUYER_HEADER, *[f"Extra {n}" for n in range(8)]]
    content = csv_bytes(header, [["A", "a.com", VERTICAL, *[""] * 8]])

    with pytest.raises(TemplateError) as raised:
        parse_upload("buyer", "list.csv", content)

    assert "Extra 4" in str(raised.value)
    assert "Extra 5" not in str(raised.value)


def test_a_file_over_the_size_cap_is_rejected_before_it_is_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(bulk_file, "MAX_FILE_BYTES", 50)
    content = csv_bytes(BUYER_HEADER, [["Acme", "acme.com", VERTICAL]] * 5)

    with pytest.raises(TemplateError, match="the file is larger than"):
        parse_upload("buyer", "list.csv", content)
