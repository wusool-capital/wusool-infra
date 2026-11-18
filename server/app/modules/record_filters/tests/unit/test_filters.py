"""Checking `filters` against each field's type, before any query."""

from datetime import UTC, date, datetime

import pytest
from pydantic import TypeAdapter, ValidationError

from app.modules.record_filters import (
    FieldCondition,
    FieldFilter,
    FieldMeta,
    FilterProblem,
    build_catalog,
    resolve_filters,
)

_ADAPTER: TypeAdapter[FieldFilter] = TypeAdapter(FieldFilter)
_CATALOG = build_catalog(
    "buyer",
    [
        FieldMeta(
            "mandate_status", "role", "mandate_status", "Mandate status", ("Active", "Paused")
        ),
        FieldMeta("target_country", "role", "target_country", "Target country", ("Oman", "UAE")),
        FieldMeta("region", "org", "region", "Region", ("GCC", "MENA"), joined_text=True),
        FieldMeta("ebitda_ceiling", "role", "ebitda_ceiling", "EBITDA ceiling"),
        FieldMeta("check_size_min", "role", "check_size_min", "Check size min"),
        FieldMeta("notes", "role", "notes", "Notes"),
        FieldMeta("profitable_only", "role", "profitable_only", "Profitable only"),
        FieldMeta(
            "last_mandate_briefing_date", "role", "last_mandate_briefing_date", "Last briefing"
        ),
    ],
)


def _resolve(**filter_: object) -> tuple[tuple[FieldCondition, ...], list[FilterProblem]]:
    return resolve_filters(_CATALOG, [_ADAPTER.validate_python(filter_)])


def test_a_money_range_becomes_a_money_condition_on_the_role() -> None:
    (condition,), problems = _resolve(field="ebitda_ceiling", op="gte", value=2e6)

    assert problems == []
    assert (condition.target, condition.column, condition.shape) == (
        "role",
        "ebitda_ceiling",
        "money",
    )
    assert condition.value == 2e6


def test_a_numeric_string_is_accepted_for_a_number() -> None:
    (condition,), _ = _resolve(field="check_size_min", op="lte", value="5000000")

    assert condition.value == 5e6


def test_an_organization_field_goes_to_the_organization_in_the_fields_own_spelling() -> None:
    (condition,), _ = _resolve(field="region", op="in", value=["gcc"])

    assert (condition.target, condition.shape) == ("org", "joined_text")
    assert condition.value == ("GCC",)


def test_a_computed_column_filters_like_any_other() -> None:
    (condition,), problems = _resolve(field="last_interaction_at", op="gte", value="2026-01-31")

    assert problems == []
    assert condition.shape == "datetime"
    assert condition.value == datetime(2026, 1, 31, tzinfo=UTC)


def test_dates_are_parsed() -> None:
    (condition,), _ = _resolve(field="last_mandate_briefing_date", op="lte", value="2026-12-01")

    assert condition.value == date(2026, 12, 1)


@pytest.mark.parametrize(
    ("filter_", "fragment"),
    [
        ({"field": "no_such", "op": "is_set"}, "not a field of a buyer"),
        ({"field": "ebitda_ceiling", "op": "contains", "value": "x"}, "does not apply"),
        ({"field": "notes", "op": "gte", "value": 1}, "does not apply"),
        ({"field": "last_interaction_at", "op": "eq", "value": "2026-01-01"}, "does not apply"),
        ({"field": "ebitda_ceiling", "op": "gte", "value": "lots"}, "takes a number"),
        ({"field": "profitable_only", "op": "eq", "value": "yes"}, "true or false"),
        ({"field": "last_mandate_briefing_date", "op": "gte", "value": "soon"}, "YYYY-MM-DD"),
        ({"field": "last_interaction_at", "op": "gte", "value": "soon"}, "ISO date"),
        ({"field": "mandate_status", "op": "eq", "value": "sleeping"}, "list_field_options"),
        ({"field": "target_country", "op": "in", "value": ["Mars"]}, "not allowed"),
    ],
)
def test_each_bad_filter_is_named(filter_: dict[str, object], fragment: str) -> None:
    conditions, problems = _resolve(**filter_)

    assert conditions == ()
    (problem,) = problems
    assert fragment in problem.message
    assert problem.field == filter_["field"]


def test_the_options_are_never_listed_in_the_error() -> None:
    _, (problem,) = _resolve(field="mandate_status", op="eq", value="sleeping")

    assert "Paused" not in problem.message


def test_every_problem_is_collected_in_one_pass() -> None:
    items = [
        _ADAPTER.validate_python({"field": "no_such", "op": "is_set"}),
        _ADAPTER.validate_python({"field": "ebitda_ceiling", "op": "gte", "value": 1}),
        _ADAPTER.validate_python({"field": "notes", "op": "gte", "value": 1}),
    ]

    conditions, problems = resolve_filters(_CATALOG, items)

    assert len(conditions) == 1
    assert [p.position for p in problems] == [1, 3]


def test_a_free_text_field_without_options_accepts_any_text() -> None:
    (condition,), problems = _resolve(field="notes", op="contains", value="fund")

    assert problems == []
    assert condition.value == "fund"


@pytest.mark.parametrize(
    "bad",
    [
        {"field": "region", "op": "like", "value": "GCC"},
        {"field": "region", "op": "in", "value": []},
        {"field": "region", "op": "in", "value": "GCC"},
        {"field": "notes", "op": "is_set", "value": 1},
        {"op": "is_set"},
    ],
)
def test_a_malformed_filter_does_not_even_parse(bad: dict[str, object]) -> None:
    with pytest.raises(ValidationError):
        _ADAPTER.validate_python(bad)
