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
    # Records of this scope read, including those with nothing in them yet.
    records_read: int = 0
    # False when nothing was read, so the writer still treats the object as unseeded.
    marked: bool = False


class AttioSeedService:
    def __init__(self, source: SeedSourcePort, sent: SentValuesPort) -> None:
        self._source = source
        self._sent = sent

    async def run(self) -> tuple[SeedReport, ...]:
        """Safe to run again: a field that already has a row is never overwritten."""
        reports: list[SeedReport] = []
        for obj in AttioObject:
            read = await self._source.read(obj)
            stored = await self._sent.seed(obj, read.rows)
            if read.records == 0:
                # Reading no records means the wrong scope or an empty page. Marking it done
                # would let the writer overwrite live values it has never seen.
                logger.error("interactions_attio_seed_empty object=%s: not marked done", obj.value)
                reports.append(SeedReport(obj, 0, 0, 0, False))
                continue
            await self._sent.mark_seeded(obj)
            logger.info(
                "interactions_attio_seeded object=%s read=%d stored=%d",
                obj.value,
                len(read.rows),
                stored,
            )
            reports.append(SeedReport(obj, len(read.rows), stored, read.records, True))
        return tuple(reports)
