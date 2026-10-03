"""Regression coverage for `is_missing`, moved from `application/enrich.py`
to `domain/missingness.py` so `discrepancies` can reuse it.
"""

import pytest

from app.modules.enrichment.domain.missingness import is_missing


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
        ({"amount": 0}, False),
        ({"amount": 0.0}, False),
    ],
)
def test_is_missing(value: object, expected: bool) -> None:
    assert is_missing(value) is expected
