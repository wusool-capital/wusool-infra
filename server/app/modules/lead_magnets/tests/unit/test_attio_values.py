"""`_values`'s money serialisation, across both tables it now serves.

`serialize_money`'s currency lookup is keyed on `(table, field)` — a
`buyer_role` money field serialised against the `seller_role` table (or vice
versa) raises `UnknownMoneyFieldError` rather than silently mislabelling the
currency, which is exactly the failure this pins: `buyer_values` passing the
wrong table name would 500 every buyer submission that gave a check size.
"""

import pytest

from app.modules.attio.providers.attio.money import UnknownMoneyFieldError
from app.modules.lead_magnets.domain.benchmark.benchmark import Band
from app.modules.lead_magnets.domain.benchmark.benchmark_routing import Quality, Routing
from app.modules.lead_magnets.domain.benchmark.benchmark_submission import BenchmarkResult
from app.modules.lead_magnets.domain.readiness.readiness import AdvisoryContent
from app.modules.lead_magnets.domain.shared.attio_values import (
    benchmark_values,
    buyer_values,
    readiness_values,
    valuation_values,
)
from app.modules.lead_magnets.domain.shared.schemas import BuyerValuesInput, ReadinessValuesInput
from app.modules.lead_magnets.domain.valuation.valuation_methods import Valuation, ValuationInputs

_BAND = Band(id="sme", label="SME", max_usd=None, ebitda_adj=1.0, rev_emp_mult=1.0, rent_mult=1.0)


def _benchmark_result(*, quartile: int) -> BenchmarkResult:
    return BenchmarkResult(
        score=50,
        band="Solidly in the middle",
        quartile=quartile,
        peer_label="IT Services",
        revenue_band=_BAND,
        sample_size=10,
        metrics={},
        percentiles={},
        flags=[],
        routing=Routing(priority="Cold", reason="No routing trigger"),
        quality=Quality("Passed", True),
        headline="",
        ebitda_adjusted=None,
        data_completeness=100,
        metrics_covered=5,
        metrics_total=5,
        implied_ev=None,
    )


def test_buyer_check_size_serialises_against_the_buyer_role_table() -> None:
    values = buyer_values(
        BuyerValuesInput(
            check_size_min=1_000_000,
            check_size_max=5_000_000,
            prior_gcc_acquisition="One deal in 2023",
            target_geography=["UAE", "KSA"],
        )
    )
    assert values["check_size_min"] == {"currency_value": 1_000_000.0}
    assert values["check_size_max"] == {"currency_value": 5_000_000.0}
    assert values["target_geography"] == ["UAE", "KSA"]
    assert values["prior_gcc_acquisition"] == "One deal in 2023"


def test_buyer_values_omits_none_rather_than_clearing_the_field() -> None:
    values = buyer_values(BuyerValuesInput())
    assert values == {}


def test_buyer_values_carries_the_qualification_note_into_acquisition_enrichment() -> None:
    values = buyer_values(BuyerValuesInput(qualification_note="Warm mandate, introduce now."))
    assert values["acquisition_enrichment"] == "Warm mandate, introduce now."


def test_an_unconfigured_table_field_pair_still_raises() -> None:
    """The guard `_values`'s `table` parameter exists to preserve: a money
    field with no configured currency for its table fails loudly rather than
    writing an unlabelled amount. `est_revenue` is a real `seller_role`
    money field with no `buyer_role` entry."""
    from app.modules.lead_magnets.domain.shared.attio_values import _BUYER_MONEY, _values

    with pytest.raises(UnknownMoneyFieldError):
        _values({"est_revenue": 1.0}, table="buyer_role", money=_BUYER_MONEY | {"est_revenue"})


def test_readiness_values_is_unaffected_by_the_table_parameter() -> None:
    """The refactor's default (`table="seller_role"`) must reproduce the
    pre-existing behaviour for every caller that does not pass one."""
    values = readiness_values(
        ReadinessValuesInput(
            score=72.5,
            band="Getting There",
            advisory=AdvisoryContent(referral=None, advisory_note=None),
            revenue_usd=1_000_000,
        )
    )
    assert values["est_revenue"] == {"currency_value": 1_000_000.0}


@pytest.mark.parametrize(
    ("quartile", "title"),
    [
        (1, "Bottom 25%"),
        (2, "Below Average"),
        (3, "Above Average"),
        (4, "Top 25%"),
    ],
)
def test_benchmark_quartile_maps_to_the_real_attio_option_title(quartile: int, title: str) -> None:
    """A real submission's Attio write failed with `Cannot find select
    option with title "2"` — `benchmark_quartile` is a select on the real
    workspace, not free text, and the raw 1-4 int isn't one of its options.
    """
    values = benchmark_values(_benchmark_result(quartile=quartile), headcount=None)
    assert values["benchmark_quartile"] == title


def test_valuation_values_records_a_genuine_zero_rather_than_dropping_it() -> None:
    """`value_company()` legitimately returns 0 for every figure when no
    method produces a usable row — `result.low or None` would make that
    indistinguishable in Attio from a valuation never attempted."""
    result = Valuation(low=0, mid=0, high=0, methods=(), dcf=None)
    inputs = ValuationInputs(revenue=0)
    values = valuation_values(result, inputs)
    assert values["valuation_low"] == {"currency_value": 0.0}
    assert values["valuation_mid"] == {"currency_value": 0.0}
    assert values["valuation_high"] == {"currency_value": 0.0}
    # `adjusted_ebitda` is never `None` (0+0 when both inputs are absent),
    # so it is always written — same "record the real zero" reasoning.
    assert values["ebitda_adjusted"] == {"currency_value": 0.0}


def test_valuation_values_writes_the_raw_submission_alongside_the_blend() -> None:
    """The three blended figures used to be all this wrote — the visitor's
    own revenue/EBITDA/owner-salary/stage/consent never reached Attio at
    all, despite the form collecting exactly those numbers."""
    result = Valuation(low=1, mid=2, high=3, methods=(), dcf=None)
    inputs = ValuationInputs(
        revenue=500_000, profit_before_tax=80_000, owner_salary=40_000, stage="Series A"
    )

    values = valuation_values(result, inputs, consent=True)

    assert values["est_revenue"] == {"currency_value": 500_000.0}
    assert values["est_ebitda"] == {"currency_value": 80_000.0}
    assert values["owner_salary"] == {"currency_value": 40_000.0}
    assert values["ebitda_adjusted"] == {"currency_value": 120_000.0}
    assert values["funding_stage"] == "Series A"
    assert values["data_consent"] is True


def test_valuation_values_drops_unentered_optional_fields() -> None:
    """`profit_before_tax`/`owner_salary`/`stage` are genuinely optional on
    the form — `None` must be omitted, not sent as a false zero/empty
    string that would overwrite a value an earlier submission wrote."""
    result = Valuation(low=1, mid=2, high=3, methods=(), dcf=None)
    inputs = ValuationInputs(revenue=500_000)

    values = valuation_values(result, inputs)

    assert "est_ebitda" not in values
    assert "owner_salary" not in values
    assert "funding_stage" not in values
    assert "data_consent" not in values


def test_benchmark_quartile_falls_back_to_the_raw_value_when_unrecognised() -> None:
    """Same fallback shape as `attio_band()`: an out-of-range quartile
    surfaces as a failed Attio option lookup rather than a silently wrong
    value."""
    values = benchmark_values(_benchmark_result(quartile=5), headcount=None)
    assert values["benchmark_quartile"] == "5"
