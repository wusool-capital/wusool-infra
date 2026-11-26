"""The valuation page's own formatting and tax helpers, run as shipped under Node.

`20-helpers.js` is Babel-flavoured JSX, so a few named top-level lines are cut out of it
rather than loading the whole file. Skipped when Node is missing."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_STATIC = Path(__file__).parents[2] / "static" / "valuation"

_HARNESS = """
import fs from "node:fs";
import vm from "node:vm";
const [data, helpers] = [process.argv[2], process.argv[3]];
const pick = (src, re) => {
  const m = src.match(re);
  if (!m) throw new Error("not found: " + re);
  return m[0];
};
const dataSrc = fs.readFileSync(data, "utf8");
const src = fs.readFileSync(helpers, "utf8");
const picks = JSON.parse(process.argv[4]).map((p) => new RegExp(p, "m"));
const code = [pick(dataSrc, /^const CUR_SYM *=.*$/m), ...picks.map((re) => pick(src, re))]
  .join("\\n");
const calls = JSON.parse(fs.readFileSync(0, "utf8"));
const out = vm.runInNewContext(`${code}\\n${JSON.stringify(calls)}.map((c) => eval(c));`, {});
process.stdout.write(JSON.stringify(out));
"""


def _run_js(picks: list[str], calls: list[str], tmp_path: Path) -> list[str | float | None]:
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    done = subprocess.run(  # noqa: S603  # a fixed command on files in this repository
        [
            str(shutil.which("node")),
            str(harness),
            str(_STATIC / "10-data.js"),
            str(_STATIC / "20-helpers.js"),
            json.dumps(picks),
        ],
        input=json.dumps(calls),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


_NEEDS_NODE = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")
_FMT_RESULT_PICKS = [r"^const CUR_RATE=.*$", r"^const fmtResult=.*$"]


@_NEEDS_NODE
def test_a_small_valuation_is_not_shown_as_zero_millions(tmp_path: Path) -> None:
    """`fmtResult(40000)` used to print "$0.0M", so a small business's low read as zero."""
    shown = _run_js(
        _FMT_RESULT_PICKS,
        [
            "fmtResult(40000)",
            "fmtResult(450000)",
            "fmtResult(999999)",
            "fmtResult(500)",
            "fmtResult(0)",
        ],
        tmp_path,
    )
    assert shown == ["$40,000", "$450,000", "$999,999", "$500", "$0"]


@_NEEDS_NODE
def test_large_amounts_still_shorten_to_millions_and_billions(tmp_path: Path) -> None:
    shown = _run_js(
        _FMT_RESULT_PICKS,
        [
            "fmtResult(1000000)",
            "fmtResult(2450000)",
            "fmtResult(1250000000)",
            "fmtResult(-3200000)",
        ],
        tmp_path,
    )
    assert shown == ["$1.0M", "$2.5M", "$1.3B", "($3.2M)"]


@_NEEDS_NODE
def test_the_result_is_converted_before_it_is_formatted(tmp_path: Path) -> None:
    """Dollars in, dirhams out: 300,000 USD is 1,101,750 AED, which is over a million."""
    shown = _run_js(
        _FMT_RESULT_PICKS,
        [
            'fmtResult(300000, "AED")',
            'fmtResult(40000, "AED")',
            "fmtResult(null)",
            "fmtResult(NaN)",
        ],
        tmp_path,
    )
    assert shown == ["AED 1.1M", "AED 146,900", "-", "-"]
