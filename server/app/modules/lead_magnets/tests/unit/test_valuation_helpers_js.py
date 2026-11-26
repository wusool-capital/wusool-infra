"""The valuation page's own formatting and tax helpers, run as shipped under Node.

`20-helpers.js` is Babel-flavoured JSX, so a few named top-level lines are cut out of it
rather than loading the whole file. Skipped when Node is missing."""

import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest
from pydantic import JsonValue

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


def _run_js(picks: list[str], calls: list[str], tmp_path: Path) -> list[JsonValue]:
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


_GATE_PICKS = [r"^function gateNumberErrors[\s\S]*?^}"]


@_NEEDS_NODE
def test_a_negative_owner_salary_or_last_raise_revenue_gets_a_field_message(
    tmp_path: Path,
) -> None:
    """The server answers 422 to both, and the page only logged it, so the lead was lost."""
    shown = _run_js(
        _GATE_PICKS,
        [
            'Object.keys(gateNumberErrors({ownerSalary:"-50000",lastRaiseRevenue:""}))',
            'Object.keys(gateNumberErrors({ownerSalary:"",lastRaiseRevenue:"-1",raised:"Yes"}))',
            'Object.keys(gateNumberErrors({ownerSalary:"-5",lastRaiseRevenue:"-5",raised:"Yes"}))',
        ],
        tmp_path,
    )
    assert shown == [["ownerSalary"], ["lastRaiseRevenue"], ["ownerSalary", "lastRaiseRevenue"]]


@_NEEDS_NODE
def test_blank_zero_and_positive_amounts_pass_and_a_loss_is_not_checked_here(
    tmp_path: Path,
) -> None:
    """Profit before tax may be negative, and a lone "-" is still being typed."""
    shown = _run_js(
        _GATE_PICKS,
        [
            'Object.keys(gateNumberErrors({ownerSalary:"",lastRaiseRevenue:""}))',
            'Object.keys(gateNumberErrors({ownerSalary:"0",lastRaiseRevenue:"250000",raised:"Yes"}))',
            'Object.keys(gateNumberErrors({ownerSalary:"-",lastRaiseRevenue:"-"}))',
            'Object.keys(gateNumberErrors({ownerSalary:"150000",lastRaisePBT:"-40000"}))',
        ],
        tmp_path,
    )
    assert shown == [[], [], [], []]


_TAX_PICKS = [r"^function getTaxRate[\s\S]*?^}", r"^const taxPct=.*$"]


@_NEEDS_NODE
def test_a_zero_tax_country_stays_at_zero(tmp_path: Path) -> None:
    """`t[geo]||20` turned Qatar and Bahrain into 20%; the server has them at 0."""
    shown = _run_js(
        _TAX_PICKS,
        [
            'getTaxRate("Qatar")',
            'getTaxRate("Bahrain")',
            'getTaxRate("Atlantis")',
            'getTaxRate("")',
        ],
        tmp_path,
    )
    assert shown == [0, 0, 20, 20]


@_NEEDS_NODE
def test_a_typed_zero_tax_rate_is_kept_and_only_a_missing_one_falls_back(tmp_path: Path) -> None:
    """`tax||20` silently changed a typed 0 to 20 because 0 is falsy."""
    shown = _run_js(
        _TAX_PICKS,
        ["taxPct(0)", "taxPct(9)", "taxPct(undefined)", "taxPct(null)", "taxPct(NaN)"],
        tmp_path,
    )
    assert shown == [0, 9, 20, 20, 20]


@_NEEDS_NODE
def test_the_page_tax_table_matches_the_server(tmp_path: Path) -> None:
    """The page and the CRM figure must tax the same geography the same way."""
    from app.modules.lead_magnets.domain.valuation.valuation import tax_rate

    source = (_STATIC / "20-helpers.js").read_text(encoding="utf-8")
    table = source[source.index("function getTaxRate") :].split("return t[geo]", 1)[0]
    page = {name: float(rate) for name, rate in re.findall(r'"([^"]+)":(\d+(?:\.\d+)?)', table)}
    assert len(page) >= 20

    names = [*page, "Atlantis", ""]
    shown = _run_js(_TAX_PICKS, [f"getTaxRate({json.dumps(n)})" for n in names], tmp_path)

    assert dict(zip(names, shown, strict=True)) == {n: tax_rate(n) for n in names}


@_NEEDS_NODE
def test_a_hidden_last_raise_field_is_not_checked(tmp_path: Path) -> None:
    """That field only shows after "Yes", so an error on it would block submit with no message."""
    shown = _run_js(
        _GATE_PICKS,
        [
            'Object.keys(gateNumberErrors({ownerSalary:"",lastRaiseRevenue:"-5",raised:"No"}))',
            'Object.keys(gateNumberErrors({ownerSalary:"",lastRaiseRevenue:"-5",raised:""}))',
        ],
        tmp_path,
    )
    assert shown == [[], []]


@_NEEDS_NODE
def test_amounts_at_the_million_boundary_and_tiny_losses_read_sensibly(tmp_path: Path) -> None:
    """Rounding must not print "$1,000,000" for just under a million, or "($0)" for a tiny loss."""
    shown = _run_js(
        _FMT_RESULT_PICKS,
        ["fmtResult(999999.6)", "fmtResult(999999.4)", "fmtResult(-0.4)", "fmtResult(-500)"],
        tmp_path,
    )
    assert shown == ["$1.0M", "$999,999", "$0", "($500)"]
