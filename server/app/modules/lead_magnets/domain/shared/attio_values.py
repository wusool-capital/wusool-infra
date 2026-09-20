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
from typing import Literal

from app.modules.attio.providers.attio.money import serialize_money
from app.modules.attio.providers.attio.write_values import ActorReferenceValue, RecordReferenceValue
from app.modules.lead_magnets.domain.benchmark.benchmark import PERCENTILE_COLUMNS
from app.modules.lead_magnets.domain.benchmark.benchmark_submission import (
    BenchmarkInputs,
    BenchmarkResult,
)
from app.modules.lead_magnets.domain.buyer_network.buyer_network import validate_target_geography
from app.modules.lead_magnets.domain.get_started.get_started import validate_sell_timeline
from app.modules.lead_magnets.domain.readiness.readiness import attio_band
from app.modules.lead_magnets.domain.shared.schemas import (
    BuyerValuesInput,
    GetStartedPayload,
    ReadinessValuesInput,
)
from app.modules.lead_magnets.domain.shared.sector_mapping import to_funding_stage
from app.modules.lead_magnets.domain.valuation.valuation_methods import Valuation, ValuationInputs

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


def benchmark_values(
    result: BenchmarkResult, inputs: BenchmarkInputs, *, consent: bool = False
) -> dict[str, object]:
    """The benchmark's own output, as `seller_role` attributes, plus the raw
    form inputs it was computed from.

    Those raw figures — `revenue`, `owner_salary`, `gross_margin_pct` and the
    rest — used to be folded into percentiles and then discarded, so a real
    submission's own numbers never reached Attio at all; the same gap
    `valuation_values()` already closed for its own raw inputs. `consent` is
    passed the same way `valuation_values()` takes it, not read off `inputs`
    — it isn't a scoring input, so it has no place on `BenchmarkInputs`.

    `funding_stage` only applies in tech mode, where `peer_key` is a funding
    stage rather than a sector (see `BenchmarkRequest.sector`'s docstring);
    SME mode's `peer_key` is a sector, mapped elsewhere via `to_sector_focus`.
    """
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
            "headcount": inputs.headcount,
            "lead_priority": result.routing.priority,
            "routing_reason": result.routing.reason,
            "quality_check": result.quality.check,
            "include_in_benchmark": result.quality.include_in_benchmark,
            "headline_flag": result.headline,
            "implied_ev_low": result.implied_ev.low if result.implied_ev else None,
            "implied_ev_high": result.implied_ev.high if result.implied_ev else None,
            "data_consent": consent,
            "revenue_last_full_year": inputs.revenue,
            "revenue_year_before": inputs.prev_revenue,
            "est_ebitda": inputs.ebitda_reported,
            "owner_salary": inputs.owner_salary,
            "ebitda_deducts_salary": inputs.salary_deducted,
            "gross_margin_pct": inputs.gross_margin_pct,
            "annual_rent_cost": inputs.rent_cost,
            "largest_customer_revenue_pct": inputs.top_customer_pct,
            "repeat_revenue_pct": inputs.recurring_pct,
            "years_active": inputs.years_active,
            "location_count": inputs.outlets,
            "days_to_get_paid": inputs.days_to_get_paid,
            "funding_stage": (to_funding_stage(inputs.peer_key) if inputs.mode == "tech" else None),
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


def valuation_values(
    result: Valuation, inputs: ValuationInputs, *, consent: bool | None = None
) -> dict[str, object]:
    """The blended valuation plus the raw submission it was computed from,
    as `seller_role` attributes.

    The three blended figures are what the seller-side team works from, and
    they are USD — the legacy `*_aed` slugs on the old lead-magnet list are a
    misnomer and are not what this writes to. `est_revenue`/`est_ebitda`/
    `owner_salary`/`ebitda_adjusted`/`funding_stage`/`data_consent` are the
    raw form inputs themselves — previously computed into the blend and then
    discarded, so a real submission's own numbers never reached Attio at
    all. `ebitda_adjusted` reuses `inputs.adjusted_ebitda`, the same
    profit-before-tax-plus-owner-salary figure benchmark already writes
    under this slug.
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
            "est_revenue": inputs.revenue,
            "est_ebitda": inputs.profit_before_tax,
            "owner_salary": inputs.owner_salary,
            "ebitda_adjusted": inputs.adjusted_ebitda,
            "funding_stage": inputs.stage,
            "data_consent": consent,
        }
    )


def get_started_values(data: GetStartedPayload) -> dict[str, object]:
    """The Get Started form's own figures, as `seller_role` attributes.

    Every value comes verbatim off the payload — there is nothing computed
    here, unlike the other four tools — so this takes the stored-payload
    model directly rather than a `*ValuesInput` wrapper it would only ever
    be constructed from.

    `sell_timeline` is the first pipeline write to that column (it was
    Slack-edit-only until now), so it goes through `validate_sell_timeline`:
    Attio only logs an unknown select option rather than rejecting it, which
    would drop the timeline silently on every submission.

    Revenue and EBITDA arrive already in USD — the page converts from its
    AED entry fields before posting, the same as the benchmark tool's
    `toCalc`. Nothing here converts.
    """
    return _values(
        {
            "est_revenue": data.revenue,
            "est_ebitda": data.ebitda,
            "years_active": data.years_active,
            "sell_timeline": (
                validate_sell_timeline(data.sell_timeline) if data.sell_timeline else None
            ),
            "data_consent": data.consent,
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


# `organizations.lead_source_detail`'s option titles (`schema.ps1`) already
# match the four lead-magnet tool names — no new Attio attribute needed.
# `"attio_webhook"` (the mirror's own sync direction, never a real
# submission) and any future tool fall through to `None`, which
# `role_writer.py` treats as "don't set this field".
_LEAD_SOURCE_DETAIL_LABELS: Mapping[str, str] = {
    "valuation": "Valuation Tool",
    "readiness": "M&A Readiness Tool",
    "benchmark": "GCC SME Benchmark",
    "buyer_network": "Buyer Form",
    "get_started": "Get Started",
}


def lead_source_detail_label(tool: str) -> str | None:
    return _LEAD_SOURCE_DETAIL_LABELS.get(tool)


def display_name(name: str | None, email: str) -> str:
    """`person.name` is required in Attio; benchmark and valuation don't
    require a name from the visitor, so this must never return an empty
    string. Falls back to the email address itself — not invented, this
    already matches real records in the live workspace, created the same
    way by the existing Attio<->Postgres sync bot for a person with no
    name on file.
    """
    stripped = (name or "").strip()
    return stripped or email


def person_values(
    *,
    name: str,
    email: str,
    organization_attio_id: str | None,
    linkedin: str | None = None,
    phone: str | None = None,
) -> dict[str, object]:
    """The write shape for a `person` create — see
    `providers/attio/person_writer.py` for the dedupe/patch-blanks rule
    this feeds into.

    `company` is a record-reference: Attio's own array shape, matching the
    one write elsewhere in this repo that already builds it
    (`attio/providers/attio/notes.py`'s `associated_deals`). Omitted
    entirely — never sent as `null` — when there is no organisation id.
    """
    values: dict[str, object] = {"name": name, "email": email}
    if organization_attio_id:
        values["company"] = RecordReferenceValue(
            target_object="organizations", target_record_id=organization_attio_id
        ).as_value()
    if linkedin:
        values["linkedin"] = linkedin
    if phone:
        values["phone"] = phone
    return values


# Attio's `deal.deal_type` option titles, and the pipeline stage every
# lead-magnet deal lands in. Both are live option titles on the custom
# `deal` object (verified 2026-09-14); `deal_stage` is `is_required` there,
# so a create that omits it is rejected outright.
DealType = Literal["Buy-side", "Sell-side"]
INBOUND_STAGE = "Inbound"

# Which reference attribute the submitting organisation goes in. A seller
# tool's visitor is the company that might sell; a buyer-network applicant
# is the acquirer. `seller_id` accepts `organizations` only, `buyer_id`
# accepts `organizations` or `person` — both are given an organisation here.
DEAL_PARTY_FIELD: Mapping[DealType, str] = {"Sell-side": "seller_id", "Buy-side": "buyer_id"}


def deal_values(
    *, name: str, org_attio_id: str, deal_type: DealType, owner_id: str
) -> dict[str, object]:
    """The write shape for a `deal` create — see
    `providers/attio/deal_writer.py` for the dedupe rule this feeds into.

    `deal_name` is always sent even though Attio does not require it: the
    Postgres mirror's `deals.name` is `NOT NULL`, and `_deal_params` would
    otherwise substitute `Unnamed Deal [<record id>]`.

    Select and status attributes take their option *title* directly, same as
    `role_writer.py`'s `sector_focus`. `deal_owner` is an actor-reference —
    the shape `values.actor` reads back on the mirror's side.
    """
    return {
        "deal_name": name,
        "deal_stage": INBOUND_STAGE,
        "deal_type": deal_type,
        "deal_owner": ActorReferenceValue(
            referenced_actor_type="workspace-member", referenced_actor_id=owner_id
        ).as_value(),
        DEAL_PARTY_FIELD[deal_type]: RecordReferenceValue(
            target_object="organizations", target_record_id=org_attio_id
        ).as_value(),
    }
