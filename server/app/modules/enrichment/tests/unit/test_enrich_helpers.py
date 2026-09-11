"""Regression coverage for `EnrichMixin`'s pure helpers — no service
construction needed, both are plain functions.
"""

from datetime import date

import pytest

from app.modules.enrichment.application.enrich import _coerce_proposed_value, _is_missing


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (None, True),
        ("", True),
        ("   ", True),
        ([], True),
        ({}, True),
        ({"amount": None}, True),
        (0, False),
        (0.0, False),
        (False, False),
        ("0", False),
        (["a"], False),
        ({"amount": 5000}, False),
    ],
)
def test_is_missing(value: object, expected: bool) -> None:
    assert _is_missing(value) is expected


def test_coerce_proposed_value_currency() -> None:
    assert _coerce_proposed_value("currency", "5000000") == 5000000.0


def test_coerce_proposed_value_number() -> None:
    assert _coerce_proposed_value("number", "20") == 20.0


def test_coerce_proposed_value_date() -> None:
    assert _coerce_proposed_value("date", "2020-01-15") == date(2020, 1, 15)


def test_coerce_proposed_value_bool() -> None:
    assert _coerce_proposed_value("bool", "true") is True
    assert _coerce_proposed_value("bool", "false") is False


def test_coerce_proposed_value_text_passthrough() -> None:
    assert _coerce_proposed_value("text", "Dubai") == "Dubai"


def test_coerce_proposed_value_invalid_currency_raises() -> None:
    with pytest.raises(ValueError):
        _coerce_proposed_value("currency", "about five million")
