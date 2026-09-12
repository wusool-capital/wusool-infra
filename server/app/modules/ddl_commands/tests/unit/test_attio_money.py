import pytest

from app.modules.attio.providers.attio.money import (
    UnknownMoneyFieldError,
    default_currency_code,
    serialize_money,
    to_postgres_money,
)


def test_organizations_funding_raised_is_usd() -> None:
    # currency_code is deliberately absent from the Attio write shape — see
    # money.py's module docstring (Attio rejects it as an unrecognized key).
    assert serialize_money("organizations", "funding_raised", 100.0) == {
        "currency_value": 100.0,
    }
    assert default_currency_code("organizations", "funding_raised") == "USD"


@pytest.mark.parametrize(
    "table,field",
    [
        ("seller_role", "est_revenue"),
        ("seller_role", "valuation_low"),
        ("seller_role", "revenue_last_full_year"),
        ("seller_role", "revenue_year_before"),
        ("seller_role", "annual_rent_cost"),
        ("seller_role", "implied_ev_low"),
        ("seller_role", "implied_ev_high"),
        ("seller_role", "ebitda_adjusted"),
        ("buyer_role", "ebitda_floor"),
        ("buyer_role", "check_size_max"),
        ("buyer_role", "ebitda_ceiling"),
        ("buyer_role", "estimated_aum"),
    ],
)
def test_role_money_fields_are_usd(table: str, field: str) -> None:
    assert serialize_money(table, field, 500.0) == {"currency_value": 500.0}
    assert default_currency_code(table, field) == "USD"


def test_unknown_field_raises() -> None:
    with pytest.raises(UnknownMoneyFieldError):
        serialize_money("seller_role", "not_a_real_field", 1.0)


def test_serialize_money_rounds_to_attios_4_decimal_limit() -> None:
    """A blended figure (several ratios multiplied together) routinely
    produces more than 4 decimal places, which Attio's API rejects outright
    (`validation_type` on `currency_value`, confirmed live against the real
    workspace)."""
    assert serialize_money("seller_role", "valuation_low", 2_683_279.502586056) == {
        "currency_value": 2_683_279.5,
    }


def test_attio_and_postgres_round_a_blended_figure_the_same_way() -> None:
    """`build_postgres_values`/`build_attio_values`
    (`ddl_commands/providers/attio/write_payload.py`) call `to_postgres_money`
    and `serialize_money` with the same raw extracted value — the two must
    round it identically, or Attio and Postgres silently disagree on the
    number for the same field on the same write."""
    raw = 2_683_279.502586056
    assert serialize_money("seller_role", "valuation_low", raw)["currency_value"] == round(raw, 2)
    assert to_postgres_money("seller_role", "valuation_low", raw)["amount"] == round(raw, 2)
