"""One calibration run: our labels against Attio's, computed in memory and written nowhere."""

from dataclasses import dataclass
from datetime import datetime

from app.modules.interactions.application.ports.record_directory import RecordDirectoryPort
from app.modules.interactions.application.ports.strength_source import StrengthSourcePort
from app.modules.interactions.application.ports.touch_reader import TouchReaderPort
from app.modules.interactions.domain.calibration import CalibrationReport, calibrate
from app.modules.interactions.domain.model import ScoringRules, StrengthLabel
from app.modules.interactions.domain.summary import summarize


@dataclass(frozen=True)
class CalibrationConfig:
    # Folded addresses of the mailboxes we read; Attio's strongest user must be one of them.
    read_mailboxes: frozenset[str]
    internal_domains: tuple[str, ...]
    rules: ScoringRules


async def run_calibration(
    source: StrengthSourcePort,
    reader: TouchReaderPort,
    directory: RecordDirectoryPort,
    config: CalibrationConfig,
    now: datetime,
) -> CalibrationReport:
    companies = await source.companies()
    touches = await reader.touches_by_organization()
    ours: dict[str, StrengthLabel | None] = {
        org_id: summarize(org_touches, now, config.rules).connection_strength
        for org_id, org_touches in touches.items()
    }
    return calibrate(
        companies,
        await directory.load(),
        ours,
        config.read_mailboxes,
        config.internal_domains,
    )
