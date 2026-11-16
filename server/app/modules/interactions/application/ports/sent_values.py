"""What the engine last sent to Attio per record and field, and what the seed found there."""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Protocol

from app.modules.interactions.domain.attio_fields import AttioObject


@dataclass(frozen=True)
class RecordValues:
    """`sent` is what the record holds in Attio. `baseline` is the live Company or Person value."""

    sent: Mapping[str, str | None]
    baseline: Mapping[str, str | None]


@dataclass(frozen=True)
class SeedRow:
    record_id: str
    field: str
    value: str | None
    baseline: str | None


class SentValuesPort(Protocol):
    async def load(self, obj: AttioObject) -> Mapping[str, RecordValues]:
        """Every record of one object that has stored values, keyed by Attio record id."""
        ...

    async def save(self, obj: AttioObject, record_id: str, fields: Mapping[str, str]) -> None:
        """Record what was just sent. The baseline is left as it was."""
        ...

    async def seed(self, obj: AttioObject, rows: Sequence[SeedRow]) -> int:
        """Store what Attio holds today. A field that already has a row is left alone."""
        ...

    async def is_seeded(self, obj: AttioObject) -> bool: ...

    async def mark_seeded(self, obj: AttioObject) -> None: ...
