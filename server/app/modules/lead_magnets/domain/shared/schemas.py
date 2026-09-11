"""Pydantic models for the shapes stored in `tool_runs.payload`.

The one explicit, scoped exception to this module's "no pydantic in
domain/application" rule — see `tests/test_architecture.py`'s allowlist,
which permits `pydantic` only for a file at exactly this path. `payload` is
validated JSON with a known shape per tool, one entry per
`api/schemas.py` request model; parsing it back out by hand with
`payload.get(key)` plus manual `isinstance` checks (the `num()`/`text()`/
`count()` closures `pipelines.py` used to repeat once per tool) is exactly
the class of bug Pydantic exists to remove.

Deliberately permissive — `extra="ignore"`, and no min/max/`ge`/`le`
constraints re-declared from `api/schemas.py`. The data was already
strictly validated once, at the API boundary, before it was stored; these
models type the *read* side, not re-enforce the write side's constraints a
second time. They also have to tolerate the write contract's own
bookkeeping keys merged into the same dict later (`stage`, `ai`, `attio`,
readiness's `score`) — `extra="ignore"` is what lets a model built to read
one part of the payload's life ignore fields a later stage added.
"""

from typing import Literal

from pydantic import BaseModel, ConfigDict


class _Payload(BaseModel):
    model_config = ConfigDict(extra="ignore")


class BenchmarkPayload(_Payload):
    """Mirrors `BenchmarkInputs`' own fields exactly — everything
    `benchmark_inputs()`/`Pipelines._benchmark()` reads from the stored
    payload."""

    mode: Literal["sme", "tech"] = "sme"
    peer_key: str = ""
    revenue: float | None = None
    prev_revenue: float | None = None
    ebitda_reported: float | None = None
    owner_salary: float | None = None
    salary_deducted: bool = False
    gross_margin_pct: float | None = None
    headcount: int | None = None
    rent_cost: float | None = None
    capital_raised: float | None = None
    top_customer_pct: float | None = None
    recurring_pct: float | None = None
    years_active: float | None = None
    outlets: int | None = None
    days_to_get_paid: int | None = None
    email: str | None = None
    geography: str | None = None


class ReadinessAnswersPayload(_Payload):
    q1: int | None = None
    q2: int | None = None
    q3: int | None = None
    q4: int | None = None
    q5: int | None = None
    q6: int | None = None
    q7: int | None = None
    q8: int | None = None
    q9: int | None = None
    q10: int | None = None
    q11: int | None = None
    q12: int | None = None
    q13: int | None = None
    q14: str | None = None
    q15: str | None = None


class ReadinessPayload(_Payload):
    name: str = ""
    company: str = ""
    sector: str = ""
    revenue: str | None = None
    country: str | None = None
    answers: ReadinessAnswersPayload = ReadinessAnswersPayload()


class ValuationCompPayload(_Payload):
    co: str = ""
    tk: str = ""
    ev: float | None = None
    rev: float | None = None
    ebitda: float | None = None


class ValuationDiscountsPayload(_Payload):
    revenue_discount_pct: float | None = None
    ebitda_discount_pct: float | None = None


class ValuationPayload(_Payload):
    revenue: float = 0.0
    profit_before_tax: float | None = None
    owner_salary: float | None = None
    sector: str | None = None
    geography: str | None = None
    stage: str | None = None
    cash: float = 0.0
    debt: float = 0.0
    comps: list[ValuationCompPayload] = []
    discounts: ValuationDiscountsPayload | None = None


class BuyerNetworkPayload(_Payload):
    org_name: str = ""
    org_type: list[str] = []
    sector_focus: list[str] = []
    target_geography: list[str] = []
    check_size_min: float | None = None
    check_size_max: float | None = None
    prior_gcc_acquisition: str | None = None
