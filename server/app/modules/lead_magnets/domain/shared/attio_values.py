"""Maps a tool's result onto Attio `seller_role` attribute values. Pure.

Separate from `providers/attio/role_writer.py` on purpose: this is a value
mapping with no I/O, so `application/` can build the payload without
importing a provider — which the module's own architecture test forbids, and
caught when this lived next to the writer.

The attribute slugs are the V2 `seller_role` ones, taken from the mirror's
own read side (`ddl_commands/persistence/attio_sync.py`) rather than
guessed; they match the Postgres column names exactly. This is deliberately
not the legacy `lead_magnet_inbound_benchmark` list the old tools write to,
whose `*_aed` slugs the Postgres mirror never reads.
"""

from collections.abc import Mapping

from app.modules.attio.providers.attio.money import serialize_money
from app.modules.lead_magnets.domain.benchmark.benchmark import PERCENTILE_COLUMNS
from app.modules.lead_magnets.domain.benchmark.benchmark_submission import BenchmarkResult
from app.modules.lead_magnets.domain.buyer_network.buyer_network import validate_target_geography
from app.modules.lead_magnets.domain.readiness.readiness import attio_band
from app.modules.lead_magnets.domain.shared.schemas import BuyerValuesInput, ReadinessValuesInput
from app.modules.lead_magnets.domain.valuation.valuation_methods import Valuation

# What a `seller_role` attribute can hold on the write side. A money field
# arrives as a bare number and is serialised into Attio's own currency shape
# by `_values`.
AttrValue = float | int | str | bool | None

# Money attributes on `seller_role`, all USD. `serialize_money` refuses a
# field it has no configured currency for, which is the guard that stops a
# new money attribute being written with an unknown denomination.
_SELLER_MONEY = frozenset(
    {
        "est_revenue",
        "est_ebitda",
        "owner_salary",
        "revenue_last_full_year",
        "revenue_year_before",
        "annual_rent_cost",
        "implied_ev_low",
        "implied_ev_high",
        "ebitda_adjusted",
        # `valuation_values()` below — configured in `money.py`'s
        # `_CURRENCY_CODE_BY_FIELD` but never actually routed through
        # `serialize_money` until now, so every valuation write sent a bare
        # float to a `currency`-type attribute instead of the
        # `{"currency_value": ...}` shape Attio's API requires for one.
        "valuation_low",
        "valuation_mid",
        "valuation_high",
    }
)

# `buyer_role`'s money attributes — a distinct set from `_SELLER_MONEY`
# because `serialize_money`'s currency lookup is keyed on `(table, field)`;
# `check_size_min` on `seller_role` isn't a configured pair, so passing the
# wrong table name here would raise `UnknownMoneyFieldError` on every buyer
# submission that gave a check size.
_BUYER_MONEY = frozenset({"check_size_min", "check_size_max"})

# `benchmark_quartile` is an Attio select, not free text — its option titles
# describe the band, not the raw 1-4 int (`benchmark_submission.py`'s
# `overall_quartile`, 1=worst, 4=best). Confirmed against the live workspace
# after a real submission's Attio write failed with `Cannot find select
# option with title "2"`.
_QUARTILE_TITLES = {
    1: "Bottom 25%",
    2: "Below Average",
    3: "Above Average",
    4: "Top 25%",
}


def _values(
    raw: Mapping[str, AttrValue],
    *,
    table: str = "seller_role",
    money: frozenset[str] = _SELLER_MONEY,
) -> dict[str, object]:
    """Drops empty values and serialises the money ones.

    A `None` is omitted rather than sent: Attio treats an explicit null as
    "clear this field", which would wipe a value an earlier tool wrote for
    the same organisation.
    """
    out: dict[str, object] = {}
    for slug, value in raw.items():
        if value is None:
            continue
        if slug in money:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"money attribute {slug} needs a number, got {type(value).__name__}"
                )
            out[slug] = serialize_money(table, slug, float(value))
        else:
            out[slug] = value
    return out


def benchmark_values(result: BenchmarkResult, *, headcount: int | None) -> dict[str, object]:
    """The benchmark's own output, as `seller_role` attributes."""
    percentiles = {
        PERCENTILE_COLUMNS[key]: value
        for key, value in result.percentiles.items()
        if value is not None
    }
    return _values(
        {
            "benchmark_score": result.score,
            "benchmark_band": result.band,
            # Falls through to the raw int for anything unrecognised, same
            # as `attio_band()` — a future quartile scheme change surfaces
            # as a failed Attio option lookup, not a silently wrong value.
            "benchmark_quartile": _QUARTILE_TITLES.get(result.quartile, str(result.quartile)),
            "ebitda_adjusted": result.ebitda_adjusted,
            "headcount": headcount,
            "lead_priority": result.routing.priority,
            "routing_reason": result.routing.reason,
            "quality_check": result.quality.check,
            "include_in_benchmark": result.quality.include_in_benchmark,
            "headline_flag": result.headline,
            "implied_ev_low": result.implied_ev.low if result.implied_ev else None,
            "implied_ev_high": result.implied_ev.high if result.implied_ev else None,
            **percentiles,
        }
    )


def readiness_values(data: ReadinessValuesInput) -> dict[str, object]:
    return _values(
        {
            "readiness_score": data.score,
            # The prompt's band wording is not an Attio option title.
            "readiness_band": attio_band(data.band),
            "recommended_referral": data.advisory.referral,
            "est_revenue": data.revenue_usd,
        }
    )


def valuation_values(result: Valuation) -> dict[str, object]:
    """The blended valuation, as `seller_role` attributes.

    The three figures are what the seller-side team works from, and they are
    USD — the legacy `*_aed` slugs on the old lead-magnet list are a misnomer
    and are not what this writes to.
    """
    return _values(
        {
            # Not `result.low or None` — `value_company()` can legitimately
            # return 0 for every figure when no method produces a usable
            # row, and `0 or None` would drop it, making a submission whose
            # valuation genuinely computed to zero indistinguishable in
            # Attio from one where valuation was never attempted.
            "valuation_low": result.low,
            "valuation_mid": result.mid,
            "valuation_high": result.high,
        }
    )


def buyer_values(data: BuyerValuesInput) -> dict[str, object]:
    """The buyer application, as `buyer_role` attributes.

    `target_geography` is a multiselect array, not run through `_values`'s
    single-value path — an empty list is a real, distinct "no answer" from
    `None` and is sent as-is rather than dropped.

    `qualification_note` lands in `acquisition_enrichment`: that column is
    explicitly excluded from `/edit-buyer`'s field list because it is "both
    manual and pipeline-written" (`ddl_commands/api/buyers.py`) — this is
    the pipeline write it was reserved for.
    """
    values = _values(
        {
            "prior_gcc_acquisition": data.prior_gcc_acquisition,
            "check_size_min": data.check_size_min,
            "check_size_max": data.check_size_max,
            "acquisition_enrichment": data.qualification_note,
        },
        table="buyer_role",
        money=_BUYER_MONEY,
    )
    if data.target_geography:
        values["target_geography"] = validate_target_geography(data.target_geography)
    return values
