"""Compare our connection-strength labels with Attio's, for the shadow week (AZM-159 PR 3).

    python -m app.modules.interactions.scripts.calibrate_strength [--mismatches PATH]

Read-only: it reads Attio and the interaction tables and writes nothing to either. It prints
counts only, never names or subjects. Run it inside the deployed container, never from a laptop
against the dev or prod database.
"""

import argparse
import asyncio
from datetime import UTC, datetime
from pathlib import Path

from app.modules.attio import get_attio_client
from app.modules.interactions.application.calibration import CalibrationConfig, run_calibration
from app.modules.interactions.config import get_settings
from app.modules.interactions.domain.addresses import team_member_of
from app.modules.interactions.domain.calibration import (
    EXACT_GATE,
    WITHIN_ONE_GATE,
    Bucket,
    CalibrationReport,
)
from app.modules.interactions.domain.model import StrengthLabel
from app.modules.interactions.persistence.database import get_sessionmaker
from app.modules.interactions.persistence.directory import SqlAlchemyRecordDirectory
from app.modules.interactions.persistence.touch_reader import SqlAlchemyTouchReader
from app.modules.interactions.providers.attio_companies import AttioStrengthSource


def render(report: CalibrationReport) -> str:
    """The report as text. Every percentage names its denominator."""
    lines = [f"Compared: {report.compared} Companies"]
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
    for bucket in Bucket:
        if bucket is not Bucket.COMPARED:
            lines.append(f"  {report.excluded.get(bucket, 0):>5}  {bucket.value}")
    return "\n".join(lines)


def _pct(rate: float | None) -> str:
    return "n/a" if rate is None else f"{rate:.1%}"


async def main(mismatches: Path | None) -> None:
    settings = get_settings()
    sessionmaker = get_sessionmaker()
    internal = settings.internal_domains
    config = CalibrationConfig(
        read_mailboxes=frozenset(team_member_of(m, internal) for m in settings.mailboxes),
        internal_domains=internal,
        rules=settings.scoring_rules(),
    )
    async with get_attio_client() as client:
        report = await run_calibration(
            AttioStrengthSource(client, internal),
            SqlAlchemyTouchReader(sessionmaker, internal),
            SqlAlchemyRecordDirectory(sessionmaker),
            config,
            datetime.now(UTC),
        )
    print(render(report))
    if mismatches is not None:
        # Record ids only, so the file holds no company names.
        mismatches.write_text("\n".join(report.mismatch_ids) + "\n", encoding="utf-8")
        print(f"\nWrote {len(report.mismatch_ids)} record ids to {mismatches}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mismatches", type=Path, default=None)
    asyncio.run(main(parser.parse_args().mismatches))
