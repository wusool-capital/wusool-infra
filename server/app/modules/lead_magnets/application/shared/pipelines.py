"""Per-tool AI pipelines, dispatched by tool name.

Deliberately not closures captured in a request handler. A run has to be
resumable by the sweeper, in a different process with nothing but the
`tool_runs` row — so everything a pipeline needs must come from `payload`,
and the dispatch must be reachable without the original request.

Benchmark's "AI" pipeline calls no model at all: its result is the
deterministic peer scoring. It goes through the same stage anyway so there
is one write contract rather than a second path for the one tool that does
not need one.
"""

import logging
from dataclasses import asdict

from app.modules.lead_magnets.application.shared.ports import LeadLLMPort
from app.modules.lead_magnets.domain.benchmark.benchmark_submission import BenchmarkInputs, evaluate
from app.modules.lead_magnets.domain.readiness.readiness import (
    ReadinessAnswers,
    build_advisory_content,
    merge_advisory,
    revenue_range_midpoint_usd,
)
from app.modules.lead_magnets.domain.shared.attio_values import (
    benchmark_values,
    buyer_values,
    readiness_values,
    valuation_values,
)
from app.modules.lead_magnets.domain.shared.prompts import (
    buyer_qualification_prompt,
    readiness_advisory_prompt,
    readiness_score_prompt,
)
from app.modules.lead_magnets.domain.shared.schemas import (
    BenchmarkPayload,
    BuyerNetworkPayload,
    BuyerValuesInput,
    ReadinessPayload,
    ReadinessResult,
    ReadinessValuesInput,
    ValuationPayload,
)
from app.modules.lead_magnets.domain.valuation.valuation_data import ListedComp
from app.modules.lead_magnets.domain.valuation.valuation_methods import (
    ValuationInputs,
    value_company,
)
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


def readiness_answers(payload: JsonObject) -> ReadinessAnswers:
    parsed = ReadinessPayload.model_validate(payload)
    return ReadinessAnswers(**parsed.answers.model_dump())


class Pipelines:
    def __init__(self, llm: LeadLLMPort) -> None:
        self._llm = llm

    async def run(self, tool: str, payload: JsonObject) -> JsonObject:
        if tool == "benchmark":
            return self._benchmark(payload)
        if tool == "valuation":
            return self._valuation(payload)
        if tool == "readiness":
            return await self._readiness(payload)
        if tool == "buyer_network":
            return await self._buyer_network(payload)
        raise NotImplementedError(f"no pipeline for tool {tool!r} yet")

    def fallback(self, tool: str, payload: JsonObject) -> JsonObject | None:
        """`None` means this tool has no fallback and the run is finished for
        good.

        Readiness is the only one: its score, band and recommendations come
        only from the model, so there is nothing to fall back to. Valuation
        and benchmark both compute their own figures — the model only picks
        the comparables that set valuation's trading multiples, so with it
        gone the DCF, transaction comps and industry research still produce a
        blended range from static sector data.
        """
        if tool == "benchmark":
            return self._benchmark(payload)
        if tool == "valuation":
            return self._valuation(payload)
        return None

    def _benchmark(self, payload: JsonObject) -> JsonObject:
        parsed = BenchmarkPayload.model_validate(payload)
        result = evaluate(BenchmarkInputs(**parsed.model_dump()))
        return {
            "entry_values": benchmark_values(result, headcount=parsed.headcount),
            "score": result.score,
            "band": result.band,
        }

    def _valuation(self, payload: JsonObject) -> JsonObject:
        """The blended valuation, computed from the submission alone.

        Serves as both the primary path and the fallback: the AI-supplied
        comparables and discount/DCF overrides are applied when the payload
        carries them (from `/analyze` and `/compare`), and omitted when it
        does not. That is what makes a sweeper resume free — no model call,
        and the same figures either way for a given payload.
        """
        inputs = _valuation_inputs(payload)
        result = value_company(inputs)
        consent = ValuationPayload.model_validate(payload).consent
        return {
            "entry_values": valuation_values(result, inputs, consent=consent),
            "low": result.low,
            "mid": result.mid,
            "high": result.high,
            "methods": [m.name for m in result.methods],
        }

    async def _readiness(self, payload: JsonObject) -> JsonObject:
        parsed = ReadinessPayload.model_validate(payload)
        answers = readiness_answers(payload)
        rules = build_advisory_content(answers)
        revenue_range = parsed.revenue

        # `score` isn't part of the original request — it's the write
        # contract's own bookkeeping, merged in separately by
        # `readiness/endpoints.py` (as `scored.model_dump()`) so this resume
        # never pays for a second scoring call. Deliberately left as a raw
        # lookup rather than a typed field on `ReadinessPayload` itself,
        # then re-hydrated into the real model here.
        stored_score = payload.get("score")
        scored = (
            ReadinessResult.model_validate(stored_score)
            if isinstance(stored_score, dict)
            else await self._llm.score_readiness(
                prompt=readiness_score_prompt(
                    founder=parsed.name,
                    business=parsed.company,
                    sector=parsed.sector,
                    revenue_range=revenue_range or "Not specified",
                    country=parsed.country or "Not specified",
                    answers=answers,
                )
            )
        )

        advisory = rules
        try:
            note = await self._llm.advise_readiness(
                prompt=readiness_advisory_prompt(
                    company=parsed.company,
                    sector=parsed.sector,
                    revenue_range=revenue_range,
                    score=scored.overallScore,
                    band=scored.scoreBand,
                    answers=answers,
                )
            )
            advisory = merge_advisory(rules, note.note)
        except Exception:  # noqa: BLE001 - the note is internal; the score is not
            logger.warning("lead_magnet_advisory_note_failed, keeping the deterministic rules")

        return {
            "entry_values": readiness_values(
                ReadinessValuesInput(
                    score=scored.overallScore,
                    band=scored.scoreBand,
                    advisory=advisory,
                    revenue_usd=revenue_range_midpoint_usd(revenue_range),
                )
            ),
            "score": scored.model_dump(),
            "advisory": asdict(advisory),
        }

    async def _buyer_network(self, payload: JsonObject) -> JsonObject:
        """The application itself is the whole record — unlike readiness,
        there is no score to compute, so there is nothing for a sweeper
        resume to reproduce and no fallback (`fallback()` returns `None` for
        this tool). The qualification note is the one best-effort addition,
        same pattern as readiness's advisory note: it never blocks or fails
        the submission.
        """
        parsed = BuyerNetworkPayload.model_validate(payload)
        check_size_min = parsed.check_size_min
        check_size_max = parsed.check_size_max
        target_geography = parsed.target_geography
        prior_gcc_acquisition = parsed.prior_gcc_acquisition

        note: str | None = None
        try:
            qualification = await self._llm.qualify_buyer(
                prompt=buyer_qualification_prompt(
                    org_name=parsed.org_name,
                    org_type=parsed.org_type,
                    sector_focus=parsed.sector_focus,
                    target_geography=target_geography,
                    check_size_min=check_size_min,
                    check_size_max=check_size_max,
                    prior_gcc_acquisition=prior_gcc_acquisition,
                )
            )
            note = qualification.note
        except Exception:  # noqa: BLE001 - the note is internal; the application is already recorded
            logger.warning("lead_magnet_buyer_qualification_failed, submitting without a note")

        return {
            "entry_values": buyer_values(
                BuyerValuesInput(
                    check_size_min=check_size_min,
                    check_size_max=check_size_max,
                    prior_gcc_acquisition=prior_gcc_acquisition,
                    target_geography=target_geography,
                    qualification_note=note,
                )
            ),
        }


def _valuation_inputs(payload: JsonObject) -> ValuationInputs:
    """Rebuilds the valuation inputs from a stored payload.

    Comparables and overrides are read from whatever `/compare` and
    `/analyze` put there. Their absence is the fallback case, not an error.

    Omitted rather than passed as `None` when a discount is genuinely
    absent — `ValuationInputs`' own per-method defaults already apply, and
    staying in sync with those defaults is free this way rather than
    duplicating the numbers here. When present, one AI-judged
    revenue/EBITDA discount pair applies to both trading and transaction
    comps alike (the model gives one opinion, not four).
    """
    parsed = ValuationPayload.model_validate(payload)
    comps = [ListedComp(**c.model_dump()) for c in parsed.comps]
    discounts = parsed.discounts

    haircuts: dict[str, float] = {}
    if discounts and discounts.revenue_discount_pct is not None:
        haircuts["trading_haircut_revenue_pct"] = discounts.revenue_discount_pct
        haircuts["transaction_haircut_revenue_pct"] = discounts.revenue_discount_pct
    if discounts and discounts.ebitda_discount_pct is not None:
        haircuts["trading_haircut_ebitda_pct"] = discounts.ebitda_discount_pct
        haircuts["transaction_haircut_ebitda_pct"] = discounts.ebitda_discount_pct

    return ValuationInputs(
        revenue=parsed.revenue,
        profit_before_tax=parsed.profit_before_tax,
        owner_salary=parsed.owner_salary,
        sector=parsed.sector,
        geography=parsed.geography,
        stage=parsed.stage,
        cash=parsed.cash,
        debt=parsed.debt,
        ai_comps=tuple(comps),
        **haircuts,
    )
