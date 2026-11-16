"""The one-time seed: record what Attio holds so the engine never overwrites it blindly."""

import logging
from dataclasses import dataclass

from app.modules.interactions.application.ports.seed_source import SeedSourcePort
from app.modules.interactions.application.ports.sent_values import SentValuesPort
from app.modules.interactions.domain.attio_fields import AttioObject

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SeedReport:
    object: AttioObject
    rows_read: int
    rows_stored: int


class AttioSeedService:
    def __init__(self, source: SeedSourcePort, sent: SentValuesPort) -> None:
        self._source = source
        self._sent = sent

    async def run(self) -> tuple[SeedReport, ...]:
        """Safe to run again: a field that already has a row is never overwritten."""
        reports: list[SeedReport] = []
        for obj in AttioObject:
            rows = await self._source.rows(obj)
            stored = await self._sent.seed(obj, rows)
            await self._sent.mark_seeded(obj)
            logger.info(
                "interactions_attio_seeded object=%s read=%d stored=%d",
                obj.value,
                len(rows),
                stored,
            )
            reports.append(SeedReport(obj, len(rows), stored))
        return tuple(reports)
