"""Regression coverage for `EnrichMixin`'s pure helpers — no service
construction needed, both are plain functions.
"""

from datetime import date

import pytest

from app.modules.enrichment.application.enrich import (
    _coerce_proposed_value,
    _constrain_to_options,
    _field_line,
    _is_missing,
)
from app.modules.enrichment.domain.field_plans import enrichable_fields_by_name_for

_TARGET_GEOGRAPHY = enrichable_fields_by_name_for("buyer")["target_geography"]
_EMPLOYEE_RANGE = enrichable_fields_by_name_for("seller")["employee_range"]
_HQ_COUNTRY = enrichable_fields_by_name_for("seller")["hq_country"]
_NOTABLE_INVESTMENTS = enrichable_fields_by_name_for("buyer")["notable_investments"]


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


def test_coerce_proposed_value_multi_select_text_splits_on_comma() -> None:
    """`target_geography` is the one `multi_select_text` field the LLM path
    ever proposes — the extraction schema's `value` is always a single
    `str`, never a real list, so this is what turns "UAE, KSA" into
    `["UAE", "KSA"]`. It's a pure shape conversion only — whether each
    resulting entry is actually in the field's vocabulary is
    `_constrain_to_options`'s job, covered separately below.
    """
    assert _coerce_proposed_value("multi_select_text", "UAE, KSA") == ["UAE", "KSA"]


def test_coerce_proposed_value_multi_select_text_single_value() -> None:
    assert _coerce_proposed_value("multi_select_text", "UAE") == ["UAE"]


def test_coerce_proposed_value_invalid_currency_raises() -> None:
    with pytest.raises(ValueError):
        _coerce_proposed_value("currency", "about five million")


def test_constrain_to_options_multi_select_text_exact_match_passes_through() -> None:
    assert _constrain_to_options(_TARGET_GEOGRAPHY, ["UAE", "KSA"]) == ["UAE", "KSA"]


def test_constrain_to_options_multi_select_text_canonicalizes_case() -> None:
    assert _constrain_to_options(_TARGET_GEOGRAPHY, ["uae", "gcc-wide"]) == ["UAE", "GCC-wide"]


def test_constrain_to_options_multi_select_text_keeps_partial_match() -> None:
    """This is the real Investcorp bug, pinned: the LLM proposed regions
    outside the fixed vocabulary alongside one that happens to match —
    the invalid members are dropped, not the whole field.
    """
    assert _constrain_to_options(_TARGET_GEOGRAPHY, ["GCC-wide", "North America"]) == ["GCC-wide"]


def test_constrain_to_options_multi_select_text_no_match_returns_none() -> None:
    assert _constrain_to_options(_TARGET_GEOGRAPHY, ["North America", "Europe", "Asia"]) is None


def test_constrain_to_options_select_valid_value() -> None:
    assert _constrain_to_options(_EMPLOYEE_RANGE, "11-50") == "11-50"


def test_constrain_to_options_select_invalid_value_returns_none() -> None:
    assert _constrain_to_options(_EMPLOYEE_RANGE, "a few hundred") is None


def test_constrain_to_options_field_without_options_passes_through_unchanged() -> None:
    assert _constrain_to_options(_NOTABLE_INVESTMENTS, "Acquired Acme Corp in 2019") == (
        "Acquired Acme Corp in 2019"
    )


def test_constrain_to_options_multi_select_as_text_is_never_constrained() -> None:
    """`hq_country` intentionally carries no `options` here — it degrades to
    free text on the Slack side (`multi_select_block`'s fallback), so an
    out-of-vocabulary country must pass through untouched, not be dropped.
    """
    assert _constrain_to_options(_HQ_COUNTRY, "Atlantis") == "Atlantis"


def test_field_line_without_options_is_unchanged() -> None:
    expected = f"- notable_investments: {_NOTABLE_INVESTMENTS.prompt_hint}"
    assert _field_line(_NOTABLE_INVESTMENTS) == expected


def test_field_line_with_options_lists_every_label() -> None:
    line = _field_line(_TARGET_GEOGRAPHY)
    for option in _TARGET_GEOGRAPHY.options:
        assert option in line
    assert "ONLY from these exact labels" in line
