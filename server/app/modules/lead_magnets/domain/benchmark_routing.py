"""Internal lead triage for the benchmark tool — priority, routing reason,
quality gates and the score band. Pure.

None of this is shown to the visitor. It populates `seller_roles`'
`lead_priority`, `routing_reason`, `quality_check`, `benchmark_review`,
`headline_flag` and `benchmark_band`, which is what the team works from.

Ported from `relay-benchmark.js`. Its thresholds were originally written in
AED and are restated at the 3.6725 peg — the AED figure is kept in a comment
on each so the commercial intent stays legible, exactly as the source does.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Literal

from app.modules.lead_magnets.domain.benchmark import js_round

Mode = Literal["sme", "tech"]

# Score -> band label, highest threshold first.
SCORE_BANDS: tuple[tuple[int, str], ...] = (
    (78, "Top decile operator"),
    (62, "Above the pack"),
    (45, "Solidly in the middle"),
    (28, "Below the peer median"),
    (0, "Early or under pressure"),
)

# Below this share of scoring weight a percentile is arithmetic rather than
# evidence: it demotes routing and keeps the record out of the dataset.
MIN_COMPLETENESS = 55

# Thresholds in USD, with the AED figure they were written as.
REV_2M_AED = 550_000  # AED 2m
REV_4M_AED = 1_100_000  # AED 4m
REV_5M_AED = 1_350_000  # AED 5m
REV_8M_AED = 2_200_000  # AED 8m
REV_10M_AED = 2_700_000  # AED 10m
REV_20M_AED = 5_400_000  # AED 20m
REVEMP_MAX = 2_200_000  # AED 8m per head
REVEMP_MIN = 4_000  # AED 15k per head

FREE_MAIL = frozenset(
    {
        "gmail.com",
        "hotmail.com",
        "outlook.com",
        "yahoo.com",
        "icloud.com",
        "live.com",
        "aol.com",
        "protonmail.com",
        "yandex.com",
        "me.com",
        "msn.com",
    }
)

PRIORITY_HOT = "Hot - partner call"
PRIORITY_WARM = "Warm - nurture"
PRIORITY_COLD = "Cold"


@dataclass(frozen=True)
class Routing:
    priority: str
    reason: str


@dataclass(frozen=True)
class Quality:
    check: str
    include_in_benchmark: bool


def score_band(score: float) -> str:
    for threshold, label in SCORE_BANDS:
        if score >= threshold:
            return label
    return SCORE_BANDS[-1][1]


def headline_flag(percentiles: Mapping[str, float | None]) -> str:
    """The weakest ranked metric, as one line for the CRM. Empty when nothing
    could be ranked."""
    ranked = [(k, v) for k, v in percentiles.items() if v is not None]
    if not ranked:
        return ""
    key, value = min(ranked, key=lambda kv: kv[1])
    return f"Weakest: {key} at {js_round(value)}th percentile"


def route(
    *,
    mode: Mode,
    revenue_usd: float | None,
    years_active: float | None,
    data_completeness: float | None,
    percentiles: Mapping[str, float | None],
) -> Routing:
    """Priority and the reasons behind it.

    Tech-enabled companies convert on different signals to trading
    businesses, so the two modes have separate trigger sets.
    """
    triggers: list[str] = []
    revenue = revenue_usd or 0
    pct = percentiles

    def at(key: str) -> float | None:
        return pct.get(key)

    if mode == "tech":
        if revenue >= REV_8M_AED:
            triggers.append("Revenue above USD 2.2m")
        if (recur := at("recur")) is not None and recur >= 70 and revenue >= REV_4M_AED:
            triggers.append("Top-tercile recurring revenue, strategic buyer profile")
        growth, rev_scale, cap_eff = at("growth"), at("revScale"), at("capEff")
        if growth is not None and growth < 25 and rev_scale is not None and rev_scale >= 50:
            triggers.append("Growth stalled at scale, sale or recap candidate")
        if cap_eff is not None and cap_eff < 25 and growth is not None and growth < 40:
            triggers.append("Capital inefficient without growth, runway conversation")
        if cap_eff is not None and cap_eff >= 75 and growth is not None and growth >= 60:
            triggers.append("Efficient and growing, premium sell-side profile")
    else:
        if revenue >= REV_10M_AED:
            triggers.append("Revenue above USD 2.7m")
        ebitda = at("ebitda")
        if revenue >= REV_5M_AED and ebitda is not None and ebitda < 25:
            triggers.append("Bottom-quartile margin at scale, turnaround or prep candidate")
        if years_active is not None and years_active >= 15:
            triggers.append("15+ years trading, succession window")
        conc = at("conc")
        if conc is not None and conc < 20 and revenue >= REV_5M_AED:
            triggers.append("Severe customer concentration, structuring conversation")

    priority = (
        PRIORITY_HOT if triggers else (PRIORITY_WARM if revenue >= REV_2M_AED else PRIORITY_COLD)
    )
    reason = "; ".join(triggers) or "No routing trigger"

    # A high score off three answered fields is not a qualified lead. Demote
    # it rather than put it in front of a partner.
    if (
        data_completeness is not None
        and data_completeness < MIN_COMPLETENESS
        and priority == PRIORITY_HOT
    ):
        priority = PRIORITY_WARM
        reason = (
            f"{reason} | Demoted: only {js_round(data_completeness)}% of scoring inputs answered"
        )

    return Routing(priority=priority, reason=reason)


def quality(
    *,
    mode: Mode,
    email: str | None,
    revenue_usd: float | None,
    headcount: int | None,
    gross_margin_pct: float | None,
    ebitda_adjusted_usd: float | None,
    prev_revenue_usd: float | None,
) -> Quality:
    """Auto-triage only. `include_in_benchmark` is **always** False here — a
    human approves a record into the dataset, and the live code is explicit
    that these checks exist to triage, not to admit.
    """
    domain = (email or "").split("@")[-1] if "@" in (email or "") else ""
    revenue = revenue_usd or 0
    ebitda_margin = (
        (ebitda_adjusted_usd / revenue) * 100
        if revenue and ebitda_adjusted_usd is not None
        else None
    )
    revenue_per_head = revenue / headcount if headcount else None

    if not revenue or not headcount:
        return Quality("Rejected", False)

    # Operating profit above gross profit is arithmetically impossible; the
    # 2-point tolerance absorbs rounding in self-reported figures.
    if (
        gross_margin_pct is not None
        and ebitda_margin is not None
        and ebitda_margin > gross_margin_pct + 2
    ):
        return Quality("Flagged - implausible", False)

    # Loss-making is normal in tech, not in a trading business.
    floor = -400 if mode == "tech" else -50
    if ebitda_margin is not None and (ebitda_margin > 65 or ebitda_margin < floor):
        return Quality("Flagged - implausible", False)

    if revenue_per_head is not None and not (REVEMP_MIN <= revenue_per_head <= REVEMP_MAX):
        return Quality("Flagged - implausible", False)

    if prev_revenue_usd and revenue / prev_revenue_usd > 12:
        return Quality("Flagged - implausible", False)

    if domain in FREE_MAIL and revenue > REV_20M_AED:
        return Quality("Flagged - free email at scale", False)

    return Quality("Passed", False)
