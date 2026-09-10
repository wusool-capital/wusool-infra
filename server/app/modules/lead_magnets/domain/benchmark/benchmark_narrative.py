"""Turns a ranked metric into the paragraph the visitor reads.

Only the extremes get copy: a metric between the two thresholds says nothing
worth a paragraph, so `flag_for` returns `None` and the report stays short
rather than padded with "you are about average".

The copy itself lives in the generated `benchmark_copy.py`.
"""

from dataclasses import dataclass
from typing import Literal

from app.modules.lead_magnets.domain.benchmark.benchmark import MetricResult, Mode, js_round

# A flag is raised only outside these bounds — good at or above 68, bad below
# 40. The `bad` copy is further split at 25 so the report can lead with the
# genuinely serious items.
GOOD_AT = 68
BAD_BELOW = 40
SEVERE_BELOW = 25

Tone = Literal["good", "mid", "bad"]


@dataclass(frozen=True)
class FlagCopy:
    bad_title: str
    bad_body: str
    good_title: str
    good_body: str


@dataclass(frozen=True)
class Flag:
    tone: Tone
    title: str
    body: str
    percentile: float


def _ordinal(value: float) -> str:
    n = js_round(value)
    if n % 100 in (11, 12, 13):
        return f"{n}th"
    return f"{n}{ {1: 'st', 2: 'nd', 3: 'rd'}.get(n % 10, 'th') }"


def _percent(value: float) -> str:
    return f"{js_round(value * 10) / 10}%"


def flag_for(
    result: MetricResult,
    *,
    peer_label: str,
    mode: Mode,
    currency: str = "USD",
) -> Flag | None:
    """The paragraph for one metric, or `None` when it is unremarkable.

    `revEmp` is the one metric whose value is a money figure rather than a
    percentage — its copy carries the `{c}` currency placeholder and prints
    a rounded thousands figure.
    """
    from app.modules.lead_magnets.domain.benchmark.benchmark_copy import (
        SME_FLAG_COPY,
        TECH_FLAG_COPY,
    )

    copy = (TECH_FLAG_COPY if mode == "tech" else SME_FLAG_COPY).get(result.key)
    if copy is None and mode == "tech":
        copy = SME_FLAG_COPY.get(result.key)
    if copy is None or result.percentile is None or result.anchors is None:
        return None

    good = result.percentile >= GOOD_AT
    bad = result.percentile < BAD_BELOW
    if not good and not bad:
        return None

    is_money = result.spec.unit == "k"
    value = str(js_round(result.value or 0)) if is_money else _percent(result.value or 0)
    median = str(js_round(result.anchors[2])) if is_money else _percent(result.anchors[2])

    title = copy.good_title if good else copy.bad_title
    body = (copy.good_body if good else copy.bad_body).format(
        v=value,
        p=_ordinal(result.percentile),
        m=median,
        s=peer_label.lower(),
        c=currency,
    )
    tone: Tone = "good" if good else ("bad" if result.percentile < SEVERE_BELOW else "mid")
    return Flag(tone=tone, title=title, body=body, percentile=result.percentile)
