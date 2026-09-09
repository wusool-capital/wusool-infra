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
from app.modules.lead_magnets.domain.benchmark import PERCENTILE_COLUMNS
from app.modules.lead_magnets.domain.benchmark_submission import BenchmarkResult
from app.modules.lead_magnets.domain.readiness import AdvisoryContent, attio_band
from app.modules.lead_magnets.domain.valuation_methods import Valuation

# What a `seller_role` attribute can hold on the write side. A money field
# arrives as a bare number and is serialised into Attio's own currency shape
# by `_values`.
AttrValue = float | int | str | bool | None

# Money attributes on `seller_role`, all USD. `serialize_money` refuses a
# field it has no configured currency for, which is the guard that stops a
# new money attribute being written with an unknown denomination.
_MONEY = frozenset(
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
    }
)


def _values(raw: Mapping[str, AttrValue]) -> dict[str, object]:
    """Drops empty values and serialises the money ones.

    A `None` is omitted rather than sent: Attio treats an explicit null as
    "clear this field", which would wipe a value an earlier tool wrote for
    the same organisation.
    """
    out: dict[str, object] = {}
    for slug, value in raw.items():
        if value is None:
            continue
        if slug in _MONEY:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                raise TypeError(
                    f"money attribute {slug} needs a number, got {type(value).__name__}"
                )
            out[slug] = serialize_money("seller_role", slug, float(value))
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
            "benchmark_quartile": str(result.quartile),
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


def readiness_values(
    *, score: float, band: str, advisory: AdvisoryContent, revenue_usd: float | None
) -> dict[str, object]:
    return _values(
        {
            "readiness_score": score,
            # The prompt's band wording is not an Attio option title.
            "readiness_band": attio_band(band),
            "recommended_referral": advisory.referral,
            "est_revenue": revenue_usd,
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
            "valuation_low": result.low or None,
            "valuation_mid": result.mid or None,
            "valuation_high": result.high or None,
        }
    )
