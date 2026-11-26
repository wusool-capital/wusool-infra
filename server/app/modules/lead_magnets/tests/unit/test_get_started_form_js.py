"""The Get Started form checks its own numbers before posting, so a typed value the server
would reject (422) shows a field message instead of a generic error.

The page script touches the DOM at load time, so only its named functions are cut out and run
under Node. Skipped when Node is missing."""

import json
import shutil
import subprocess
from pathlib import Path

import pytest

_SCRIPT = Path(__file__).parents[2] / "static" / "get-started" / "10-main.js"

_HARNESS = """
import fs from "node:fs";
import vm from "node:vm";
const src = fs.readFileSync(process.argv[2], "utf8");
const pick = (name) => {
  const m = src.match(new RegExp(`^function ${name}\\\\(.*?^}`, "ms"));
  if (!m) throw new Error("function not found: " + name);
  return m[0];
};
const code = ["num", "toUsd", "strictNum", "fieldErrors"]
  .filter((n) => new RegExp(`^function ${n}\\\\(`, "m").test(src))
  .map(pick)
  .join("\\n");
const calls = JSON.parse(fs.readFileSync(0, "utf8"));
const out = vm.runInNewContext(`const FX = 3.6725;\\n${code}\\n` +
  `${JSON.stringify(calls)}.map((c) => eval(c));`, {});
process.stdout.write(JSON.stringify(out));
"""


def _run_js(calls: list[str], tmp_path: Path) -> list[object]:
    harness = tmp_path / "harness.mjs"
    harness.write_text(_HARNESS, encoding="utf-8")
    done = subprocess.run(  # noqa: S603  # a fixed command on files in this repository
        [str(shutil.which("node")), str(harness), str(_SCRIPT)],
        input=json.dumps(calls),
        capture_output=True,
        text=True,
        check=False,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


_NEEDS_NODE = pytest.mark.skipif(shutil.which("node") is None, reason="node is not installed")


@_NEEDS_NODE
def test_a_number_field_no_longer_reads_text_as_a_number(tmp_path: Path) -> None:
    """`parseFloat` made "12abc" into 12 and "1e3" into 1000."""
    shown = _run_js(
        ['num("12abc")', 'num("1e3")', 'num("1,200,000")', 'num("-5")', 'num("8.5")', 'num("")'],
        tmp_path,
    )
    assert shown == [None, None, 1200000, -5, 8.5, None]


@_NEEDS_NODE
def test_fractional_years_and_negative_revenue_get_a_field_message(tmp_path: Path) -> None:
    """The server takes whole years and non-negative revenue, and answers 422 otherwise."""
    shown = _run_js(
        [
            'Object.keys(fieldErrors({revenue:"1000000",ebitda:"200000",years:"8.5"}))',
            'Object.keys(fieldErrors({revenue:"-5",ebitda:"200000",years:"8"}))',
            'Object.keys(fieldErrors({revenue:"1000000",ebitda:"200000",years:"-1"}))',
            'Object.keys(fieldErrors({revenue:"12abc",ebitda:"1e3",years:"8"}))',
        ],
        tmp_path,
    )
    assert shown == [["years"], ["revenue"], ["years"], ["revenue", "ebitda"]]


@_NEEDS_NODE
def test_valid_values_pass_and_a_loss_is_allowed(tmp_path: Path) -> None:
    """A loss-making business is a real submission, so EBITDA may be negative."""
    shown = _run_js(
        [
            'Object.keys(fieldErrors({revenue:"12,000,000",ebitda:"2,400,000",years:"8"}))',
            'Object.keys(fieldErrors({revenue:"0",ebitda:"-150000",years:"0"}))',
            'Object.keys(fieldErrors({revenue:"500",ebitda:"-0.5",years:"8.0"}))',
        ],
        tmp_path,
    )
    assert shown == [[], [], []]


@_NEEDS_NODE
def test_dirhams_are_still_converted_to_whole_dollars(tmp_path: Path) -> None:
    assert _run_js(['toUsd("3,672,500")', 'toUsd("abc")'], tmp_path) == [1000000, None]
