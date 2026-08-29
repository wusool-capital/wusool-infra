import pytest

from ddl_commands.shared.attio.money import (
    UnknownMoneyFieldError,
    default_currency_code,
    serialize_money,
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
        ("buyer_role", "ebitda_floor"),
        ("buyer_role", "check_size_max"),
    ],
)
def test_role_money_fields_are_usd(table: str, field: str) -> None:
    assert serialize_money(table, field, 500.0) == {"currency_value": 500.0}
    assert default_currency_code(table, field) == "USD"


def test_unknown_field_raises() -> None:
    with pytest.raises(UnknownMoneyFieldError):
        serialize_money("seller_role", "not_a_real_field", 1.0)
