"""Compare our connection-strength labels with Attio's, for the shadow week (AZM-159 PR 3).

    python -m app.modules.interactions.scripts.calibrate_strength
        [--mismatches PATH] [--scores PATH]

Read-only: it reads Attio and the interaction tables and writes nothing to either. It prints
counts only, never names or subjects. Run it inside the deployed container, never from a laptop
against the dev or prod database.
"""

import argparse
import asyncio
import csv
import io
from pathlib import Path

from app.modules.interactions.bootstrap import run_strength_calibration
from app.modules.interactions.domain.calibration import (
    EXACT_GATE,
    WITHIN_ONE_GATE,
    Bucket,
    CalibrationReport,
)
from app.modules.interactions.domain.model import StrengthLabel


def render(report: CalibrationReport) -> str:
    """The report as text. Every percentage names its denominator."""
    lines = [f"Compared: {report.compared} Companies"]
    if report.no_interactions:
        lines.append(f"  of which no interactions, counted Very weak: {report.no_interactions}")
    if report.compared:
        lines += [
            f"Exact match:      {report.exact}/{report.compared} = {_pct(report.exact_rate)}"
            f"  (gate {EXACT_GATE:.0%})",
            f"Within one level: {report.within_one}/{report.compared} = "
            f"{_pct(report.within_one_rate)}  (gate {WITHIN_ONE_GATE:.0%})",
            f"Gate: {'PASS' if report.passes_gate else 'FAIL'}",
        ]
    labels = [label.value for label in StrengthLabel]
    lines += ["", "Rows are Attio's label, columns ours:", "  " + " | ".join(labels)]
    lines += [f"  {label}: {list(row)}" for label, row in zip(labels, report.matrix, strict=True)]
    lines += ["", "Left out of the comparison:"]
    lines += [f"  {report.excluded.get(bucket, 0):>5}  {bucket.value}" for bucket in Bucket]
    return "\n".join(lines)


def scores_csv(report: CalibrationReport) -> str:
    """Record id, Attio's label and our raw score; blank when we have no interactions."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(["record_id", "attio_label", "our_score"])
    for row in report.scores:
        score = "" if row.our_score is None else f"{row.our_score:.4f}"
        writer.writerow([row.record_id, row.attio_label.value, score])
    return out.getvalue()


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.1%}"


async def main(mismatches: Path | None, scores: Path | None) -> None:
    report = await run_strength_calibration()
    print(render(report))
    if mismatches is not None:
        # Record ids only, so the file holds no company names.
        mismatches.write_text("\n".join(report.mismatch_ids) + "\n", encoding="utf-8")
        print(f"\nWrote {len(report.mismatch_ids)} record ids to {mismatches}")
    if scores is not None:
        # Ids, labels and numbers only: nothing that names a company or a person.
        scores.write_text(scores_csv(report), encoding="utf-8")
        print(f"\nWrote {len(report.scores)} score rows to {scores}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mismatches", type=Path, default=None)
    parser.add_argument("--scores", type=Path, default=None)
    args = parser.parse_args()
    asyncio.run(main(args.mismatches, args.scores))
