"""Attio `currency` attribute write shape — `{"currency_value": <number>}`
only. `currency_code` is fixed per attribute in Attio's own workspace
config (`config.currency.default_currency_code`), not settable per-write —
confirmed live 2026-08-17 the hard way: including it raises `Attio API
error 400: ... "Unrecognized key(s) in object: 'currency_code'"`. The
per-(table, field) mapping below still exists and is still load-bearing —
it's what tells the *Postgres* write which currency the number is actually
in (`to_postgres_money`), since Postgres has no server-side default the way
Attio's attribute config does.
"""

from typing import TypedDict


class AttioCurrencyWrite(TypedDict):
    currency_value: float


class MoneyJson(TypedDict):
    """Postgres's own money shape (`{"amount", "currency"}`), matching what
    `database/sync-postgres.ps1` already writes — read back by
    `attio.providers.attio.values.money`, written by `to_postgres_money`.
    """

    amount: float
    currency: str | None

# organizations.funding_raised -> USD; every buyer_role/seller_role money
# field -> USD. Keyed by (table, field) so identically-named fields on
# different tables can't be confused.
_CURRENCY_CODE_BY_FIELD = {
    ("organizations", "funding_raised"): "USD",
    ("buyer_role", "ebitda_floor"): "USD",
    ("buyer_role", "check_size_min"): "USD",
    ("buyer_role", "check_size_max"): "USD",
    ("buyer_role", "ev_ceiling"): "USD",
    ("buyer_role", "ebitda_ceiling"): "USD",
    ("buyer_role", "estimated_aum"): "USD",
    ("seller_role", "est_revenue"): "USD",
    ("seller_role", "est_ebitda"): "USD",
    ("seller_role", "owner_salary"): "USD",
    ("seller_role", "valuation_low"): "USD",
    ("seller_role", "valuation_mid"): "USD",
    ("seller_role", "valuation_high"): "USD",
    ("seller_role", "revenue_last_full_year"): "USD",
    ("seller_role", "revenue_year_before"): "USD",
    ("seller_role", "annual_rent_cost"): "USD",
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


def serialize_money(table: str, field: str, amount: float) -> AttioCurrencyWrite:
    """`default_currency_code` is still called here (not just to validate
    `(table, field)` is a known money field) — the same guard against a
    field slipping through unconfigured that every other caller of this
    module relies on, even though the returned code isn't part of the
    payload itself.
    """
    default_currency_code(table, field)
    return {"currency_value": amount}


def to_postgres_money(table: str, field: str, amount: float) -> MoneyJson:
    """Same fixed currency code as the Attio write, so the two can never
    disagree on currency."""
    return {"amount": amount, "currency": default_currency_code(table, field)}
