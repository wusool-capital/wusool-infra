"""Values Claude sends as JSON reach the write in the type the field stores. A date sent
as "2003-07-01" used to reach the Attio payload as text and crash `serialize_date`."""

from datetime import date

import pytest

from app.modules.ddl_commands.api.bulk_columns import routes_for
from app.modules.ddl_commands.api.bulk_store import UploadKind
from app.modules.ddl_commands.api.bulk_upload import UploadRow, route_fields

_DATE_FIELDS: list[tuple[UploadKind, str]] = [
    ("seller", "foundation_date"),
    ("seller", "last_attempt_date"),
    ("seller", "re_engage_date"),
    ("buyer", "last_mandate_briefing_date"),
    ("buyer", "foundation_date"),
]


@pytest.mark.parametrize(("kind", "key"), _DATE_FIELDS)
def test_a_date_sent_as_text_becomes_a_date(kind: UploadKind, key: str) -> None:
    routed = route_fields(kind, 1, {key: "2003-07-01"})

    written = {**routed.org_extracted, **routed.role_extracted}
    assert routed.problems == ()
    assert written[routes_for(kind)[key].name] == date(2003, 7, 1)


@pytest.mark.parametrize("bad", ["July 2003", "2003-13-01", "", "1.0"])
def test_a_date_that_is_not_iso_is_refused_with_the_format(bad: str) -> None:
    routed = route_fields("seller", 1, {"foundation_date": bad})

    if bad == "":
        assert routed.problems == ()  # blank on an add means "not given"
        assert "foundation_date" not in routed.org_extracted
    else:
        (problem,) = routed.problems
        assert problem.kind == "invalid" and problem.field == "foundation_date"
        assert "YYYY-MM-DD" in problem.message


def test_numbers_and_booleans_sent_as_text_are_typed() -> None:
    routed = route_fields(
        "seller",
        1,
        {
            "gross_margin_pct": "18",
            "years_active": "23",
            "revenue_last_full_year": "94827000000",
            "ebitda_deducts_salary": "yes",
        },
    )

    assert routed.problems == ()
    assert routed.role_extracted["gross_margin_pct"] == 18.0
    assert routed.role_extracted["years_active"] == 23
    assert routed.role_extracted["revenue_last_full_year"] == 94827000000.0
    assert routed.role_extracted["ebitda_deducts_salary"] is True


def test_a_list_for_a_comma_joined_multi_select_is_joined() -> None:
    options = routes_for("seller")["hq_country"].spec.options
    row: UploadRow = {"hq_country": [options[0], options[1]]}

    routed = route_fields("seller", 1, row)

    assert routed.problems == ()
    assert routed.org_extracted["hq_country"] == f"{options[0]}, {options[1]}"


def test_a_value_of_the_wrong_kind_says_what_the_field_takes() -> None:
    routed = route_fields("seller", 1, {"years_active": "twenty", "ebitda_deducts_salary": "maybe"})

    assert {p.field: p.message for p in routed.problems} == {
        "years_active": "invalid 'years_active': must be a whole number",
        "ebitda_deducts_salary": "invalid 'ebitda_deducts_salary': use Yes or No",
    }


def test_a_pydantic_type_error_is_worded_for_the_sender() -> None:
    routed = route_fields("seller", 1, {"description": ["not", "text"]})

    (problem,) = routed.problems
    assert problem.message == "invalid 'description': must be text"
    assert problem.error_type == "string_type"


@pytest.mark.parametrize(
    "text", ["2003-07-01T09:30:00", "2003-07-01T09:30:00Z", "2003-07-01 09:30:00"]
)
def test_a_date_and_time_for_a_date_field_keeps_its_date(text: str) -> None:
    routed = route_fields("seller", 1, {"foundation_date": text})

    assert routed.problems == ()
    assert routed.org_extracted["foundation_date"] == date(2003, 7, 1)


def test_a_text_for_a_list_valued_field_becomes_its_list() -> None:
    spec = routes_for("buyer")["target_region"].spec
    options = spec.options
    row: UploadRow = {"target_region": f"{options[0]};{options[1]}"}

    routed = route_fields("buyer", 1, row)

    assert routed.problems == ()
    assert routed.role_extracted["target_region"] == [options[0], options[1]]


def test_a_text_for_a_list_valued_field_must_still_be_allowed_values() -> None:
    routed = route_fields("buyer", 1, {"target_region": "Atlantis"})

    (problem,) = routed.problems
    assert problem.field == "target_region" and problem.kind == "invalid"
