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

from app.modules.lead_magnets.application.ports import LeadLLMPort
from app.modules.lead_magnets.domain.attio_values import benchmark_values, readiness_values
from app.modules.lead_magnets.domain.benchmark_submission import BenchmarkInputs, evaluate
from app.modules.lead_magnets.domain.prompts import (
    readiness_advisory_prompt,
    readiness_score_prompt,
)
from app.modules.lead_magnets.domain.readiness import (
    ReadinessAnswers,
    build_advisory_content,
    merge_advisory,
    revenue_range_midpoint_usd,
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
        if tool == "readiness":
            return await self._readiness(payload)
        raise NotImplementedError(f"no pipeline for tool {tool!r} yet")

    def fallback(self, tool: str, payload: JsonObject) -> JsonObject | None:
        """`None` means this tool has no fallback and the run is finished for
        good. Readiness is the only one: its score, band and recommendations
        come only from the model."""
        if tool == "benchmark":
            return self._benchmark(payload)
        return None

    def _benchmark(self, payload: JsonObject) -> JsonObject:
        result = evaluate(benchmark_inputs(payload))
        return {
            "entry_values": benchmark_values(result, headcount=payload.get("headcount")),
            "score": result.score,
            "band": result.band,
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
