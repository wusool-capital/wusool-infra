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
from app.modules.lead_magnets.domain.valuation.valuation_data import ListedComp
from app.modules.lead_magnets.domain.valuation.valuation_methods import (
    ValuationInputs,
    value_company,
)
from app.modules.utilities.domain.json_types import JsonObject

logger = logging.getLogger(__name__)


def benchmark_inputs(payload: JsonObject) -> BenchmarkInputs:
    """Rebuilds the scoring inputs from a stored payload, so a resume scores
    identically to the original request.

    Written out rather than splatted: `mode` is a `Literal` and the flags are
    non-optional, so a `**dict` would silently widen both.
    """

    def num(key: str) -> float | None:
        value = payload.get(key)
        return float(value) if isinstance(value, (int, float)) else None

    def count(key: str) -> int | None:
        value = payload.get(key)
        return int(value) if isinstance(value, (int, float)) else None

    def text(key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) else None

    return BenchmarkInputs(
        mode="tech" if payload.get("mode") == "tech" else "sme",
        peer_key=text("peer_key") or "",
        revenue=num("revenue"),
        prev_revenue=num("prev_revenue"),
        ebitda_reported=num("ebitda_reported"),
        owner_salary=num("owner_salary"),
        salary_deducted=bool(payload.get("salary_deducted")),
        gross_margin_pct=num("gross_margin_pct"),
        headcount=count("headcount"),
        rent_cost=num("rent_cost"),
        capital_raised=num("capital_raised"),
        top_customer_pct=num("top_customer_pct"),
        recurring_pct=num("recurring_pct"),
        years_active=num("years_active"),
        outlets=count("outlets"),
        days_to_get_paid=count("days_to_get_paid"),
        email=text("email"),
        geography=text("geography"),
    )


def readiness_answers(payload: JsonObject) -> ReadinessAnswers:
    raw = payload.get("answers") or {}
    return ReadinessAnswers(**{k: v for k, v in raw.items() if k.startswith("q")})


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
        result = evaluate(benchmark_inputs(payload))
        return {
            "entry_values": benchmark_values(result, headcount=payload.get("headcount")),
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
        result = value_company(_valuation_inputs(payload))
        return {
            "entry_values": valuation_values(result),
            "low": result.low,
            "mid": result.mid,
            "high": result.high,
            "methods": [m.name for m in result.methods],
        }

    async def _readiness(self, payload: JsonObject) -> JsonObject:
        answers = readiness_answers(payload)
        rules = build_advisory_content(answers)
        revenue_range = payload.get("revenue")

        scored = payload.get("score")
        if not isinstance(scored, dict):
            scored = await self._llm.score_readiness(
                prompt=readiness_score_prompt(
                    founder=payload.get("name") or "",
                    business=payload.get("company") or "",
                    sector=payload.get("sector") or "",
                    revenue_range=revenue_range or "Not specified",
                    country=payload.get("country") or "Not specified",
                    answers=answers,
                )
            )

        advisory = rules
        try:
            note = await self._llm.advise_readiness(
                prompt=readiness_advisory_prompt(
                    company=payload.get("company"),
                    sector=payload.get("sector"),
                    revenue_range=revenue_range,
                    score=scored["overallScore"],
                    band=scored["scoreBand"],
                    answers=answers,
                )
            )
            advisory = merge_advisory(rules, note.get("note"))
        except Exception:  # noqa: BLE001 - the note is internal; the score is not
            logger.warning("lead_magnet_advisory_note_failed, keeping the deterministic rules")

        return {
            "entry_values": readiness_values(
                score=scored["overallScore"],
                band=scored["scoreBand"],
                advisory=advisory,
                revenue_usd=revenue_range_midpoint_usd(revenue_range),
            ),
            "score": scored,
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
        check_size_min = payload.get("check_size_min")
        check_size_max = payload.get("check_size_max")
        org_type = [v for v in payload.get("org_type") or [] if isinstance(v, str)]
        sector_focus = [v for v in payload.get("sector_focus") or [] if isinstance(v, str)]
        target_geography = [v for v in payload.get("target_geography") or [] if isinstance(v, str)]
        prior_gcc_acquisition = payload.get("prior_gcc_acquisition")

        note: str | None = None
        try:
            qualification = await self._llm.qualify_buyer(
                prompt=buyer_qualification_prompt(
                    org_name=payload.get("org_name") or "",
                    org_type=org_type,
                    sector_focus=sector_focus,
                    target_geography=target_geography,
                    check_size_min=check_size_min,
                    check_size_max=check_size_max,
                    prior_gcc_acquisition=prior_gcc_acquisition,
                )
            )
            note = qualification.get("note")
        except Exception:  # noqa: BLE001 - the note is internal; the application is already recorded
            logger.warning("lead_magnet_buyer_qualification_failed, submitting without a note")

        return {
            "entry_values": buyer_values(
                check_size_min=check_size_min,
                check_size_max=check_size_max,
                prior_gcc_acquisition=prior_gcc_acquisition,
                target_geography=target_geography,
                qualification_note=note,
            ),
        }


def _valuation_inputs(payload: JsonObject) -> ValuationInputs:
    """Rebuilds the valuation inputs from a stored payload.

    Comparables and overrides are read from whatever `/compare` and
    `/analyze` put there. Their absence is the fallback case, not an error.
    """

    def num(key: str) -> float | None:
        value = payload.get(key)
        return float(value) if isinstance(value, (int, float)) else None

    def text(key: str) -> str | None:
        value = payload.get(key)
        return value if isinstance(value, str) else None

    comps: list[ListedComp] = []
    for raw in payload.get("comps") or []:
        if not isinstance(raw, dict):
            continue
        comps.append(
            ListedComp(
                co=str(raw.get("co", "")),
                tk=str(raw.get("tk", "")),
                ev=raw.get("ev"),
                rev=raw.get("rev"),
                ebitda=raw.get("ebitda"),
            )
        )

    discounts = payload.get("discounts")
    haircut_revenue = 50.0
    haircut_ebitda = 50.0
    if isinstance(discounts, dict):
        haircut_revenue = float(discounts.get("revenue_discount_pct") or haircut_revenue)
        haircut_ebitda = float(discounts.get("ebitda_discount_pct") or haircut_ebitda)

    return ValuationInputs(
        revenue=num("revenue") or 0.0,
        profit_before_tax=num("profit_before_tax"),
        owner_salary=num("owner_salary"),
        sector=text("sector"),
        geography=text("geography"),
        stage=text("stage"),
        cash=num("cash") or 0.0,
        debt=num("debt") or 0.0,
        haircut_revenue_pct=haircut_revenue,
        haircut_ebitda_pct=haircut_ebitda,
        ai_comps=tuple(comps),
    )
