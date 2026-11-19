"""The flag paragraphs show each metric in its own unit. Revenue for stage is dollars and
revenue per dollar raised is a multiple; both used to print as a percentage ("At 40000% ...").
The browser keeps its own copy of this text, so a parity test runs it and compares."""

import json
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

from app.modules.lead_magnets.domain.benchmark.benchmark import MetricResult, MetricSpec, Mode
from app.modules.lead_magnets.domain.benchmark.benchmark_narrative import flag_for

_STATIC = Path(__file__).parents[2] / "static" / "benchmark"
_SEED_LABEL = "Seed or pre-Series A"
_REV_SCALE = (100_000.0, 150_000.0, 500_000.0, 2_750_000.0, 7_200_000.0)
_CAP_EFF = (0.04, 0.09, 0.21, 0.55, 1.23)
_GROWTH = (76.0, 117.0, 150.0, 267.0, 400.0)

_SPECS = {
    "$": MetricSpec(label="Revenue for stage", unit="$", higher_is_better=True, weight=15),
    "x": MetricSpec(label="Revenue per $ raised", unit="x", higher_is_better=True, weight=20),
    "%": MetricSpec(label="Revenue growth", unit="%", higher_is_better=True, weight=25),
}


@dataclass(frozen=True)
class Case:
    key: str
    unit: str
    value: float
    percentile: float
    anchors: tuple[float, ...]
    mode: Mode = "tech"


_CASES = [
    Case("revScale", "$", 40_000.0, 1.0, _REV_SCALE),
    Case("revScale", "$", 3_200_000.0, 80.0, _REV_SCALE),
    Case("revScale", "$", 400.0, 1.0, _REV_SCALE),
    Case("revScale", "$", 1_250_000_000.0, 99.0, (1e6, 2e6, 5e6, 2.75e9, 7.2e9)),
    Case("capEff", "x", 0.04, 5.0, _CAP_EFF),
    Case("capEff", "x", 0.7, 90.0, _CAP_EFF),
    Case("growth", "%", 100.0, 18.78, _GROWTH),
]


def _python_body(case: Case) -> str:
    result = MetricResult(
        key=case.key,
        value=case.value,
        percentile=case.percentile,
        quartile=1,
        anchors=case.anchors,
        spec=_SPECS[case.unit],
    )
    flag = flag_for(result, peer_label=_SEED_LABEL, mode=case.mode)
    assert flag is not None
    return flag.body


def test_revenue_for_stage_is_shown_in_dollars() -> None:
    body = _python_body(_CASES[0])

    assert body.startswith("At $40k you are in the 1st percentile of seed or pre-series a")
    assert "%" not in body


def test_a_large_or_small_amount_is_shortened_or_left_whole() -> None:
    assert _python_body(_CASES[1]).startswith("$3.2m puts you in the 80th percentile")
    assert _python_body(_CASES[2]).startswith("At $400 you")
    assert _python_body(_CASES[3]).startswith("$1.3bn puts you in the 99th percentile")


def test_capital_efficiency_reads_as_dollars_of_revenue_per_dollar_raised() -> None:
    bad = _python_body(_CASES[4])
    good = _python_body(_CASES[5])

    assert bad.startswith("You generate $0.04 of revenue per dollar raised, against a peer median")
    assert "median of $0.21 at seed or pre-series a" in bad
    assert good.startswith("At $0.70 of revenue per dollar raised you are in the 90th percentile")


def test_a_percentage_metric_is_still_a_percentage() -> None:
    assert "Revenue moved 100% against a peer median near 150%" in _python_body(_CASES[6])


@pytest.mark.parametrize(
    ("value", "shown"),
    [(12.34, "12.3%"), (12.0, "12%"), (0.04, "0%"), (-8.0, "-8%"), (99.95, "100%")],
)
def test_a_percentage_prints_one_decimal_and_drops_a_trailing_zero(
    value: float, shown: str
) -> None:
    from app.modules.lead_magnets.domain.benchmark.benchmark_narrative import _percent

    assert _percent(value) == shown


_HARNESS = """
import fs from "node:fs";
import vm from "node:vm";
const [dir, raw] = [process.argv[2], fs.readFileSync(0, "utf8")];
const src = ["30-helpers.js", "50-narrative.js"]
  .map((f) => fs.readFileSync(`${dir}/${f}`, "utf8")).join("\\n")
  .replace(/^setMode\\([^\\n]*\\);?\\s*$/m, "");
const dom = new Proxy(function () {}, { get: () => dom, apply: () => dom, set: () => true });
const ctx = vm.createContext({ document: dom, window: dom, localStorage: dom,
  DATA: { metrics: {}, techMetrics: {}, sectors: {}, stages: {}, bands: [] } });
const cases = JSON.parse(raw);
const out = vm.runInContext(`${src}
MODE = "tech";
${JSON.stringify(cases)}.map((c) => flagFor(c.key,
  { pct: c.percentile, value: c.value, anchors: c.anchors, meta: { unit: c.unit } },
  c.label).body);`, ctx);
process.stdout.write(JSON.stringify(out));
"""


@pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
def test_the_browser_script_writes_the_same_flag_text(tmp_path: Path) -> None:
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    cases = [
        {
            "key": c.key,
            "unit": c.unit,
            "value": c.value,
            "percentile": c.percentile,
            "anchors": list(c.anchors),
            "label": _SEED_LABEL,
        }
        for c in _CASES
    ]

    done = subprocess.run(  # noqa: S603  # a fixed command on files in this repository
        [str(shutil.which("node")), str(harness), str(_STATIC)],
        input=json.dumps(cases),
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )

    assert done.returncode == 0, done.stderr
    assert json.loads(done.stdout) == [_python_body(c) for c in _CASES]
