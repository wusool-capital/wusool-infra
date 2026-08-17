"""Attio `currency` attribute write shape — confirmed live by the data
engineer, matching what `database/sync-postgres.ps1` already reads:
`{"currency_value": <number>, "currency_code": "<CODE>"}`.

`currency_code` is fixed per field, not user input — confirmed live against
each attribute's `config.currency.default_currency_code`, not uniform AED
as the historical migration config assumed.
"""

# organizations.funding_raised -> USD; every buyer_role/seller_role money
# field -> AED. Keyed by (table, field) so identically-named fields on
# different tables can't be confused.
_CURRENCY_CODE_BY_FIELD = {
    ("organizations", "funding_raised"): "USD",
    ("buyer_role", "ebitda_floor"): "AED",
    ("buyer_role", "check_size_min"): "AED",
    ("buyer_role", "check_size_max"): "AED",
    ("buyer_role", "ev_ceiling"): "AED",
    ("seller_role", "est_revenue"): "AED",
    ("seller_role", "est_ebitda"): "AED",
    ("seller_role", "owner_salary"): "AED",
    ("seller_role", "valuation_low"): "AED",
    ("seller_role", "valuation_mid"): "AED",
    ("seller_role", "valuation_high"): "AED",
}


class UnknownMoneyFieldError(Exception):
    pass


def default_currency_code(table: str, field: str) -> str:
    """The Postgres side uses the same fixed code — one number input in
    Slack, one currency for both writes, so Attio and Postgres can never
    disagree on what currency a value is in.
    """
    key = (table, field)
    if key not in _CURRENCY_CODE_BY_FIELD:
        raise UnknownMoneyFieldError(f"No configured currency code for {table}.{field}")
    return _CURRENCY_CODE_BY_FIELD[key]


def serialize_money(table: str, field: str, amount: float) -> dict:
    return {"currency_value": amount, "currency_code": default_currency_code(table, field)}


def to_postgres_money(table: str, field: str, amount: float) -> dict:
    """Postgres's own money shape (`{"amount", "currency"}`, matching what
    `database/sync-postgres.ps1` already writes) — same fixed currency code
    as the Attio write, so the two can never disagree on currency.
    """
    return {"amount": amount, "currency": default_currency_code(table, field)}
