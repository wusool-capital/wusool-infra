"""What Attio holds today, read once before the engine writes anything."""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol

from app.modules.interactions.application.ports.sent_values import SeedRow
from app.modules.interactions.domain.attio_fields import AttioObject


@dataclass(frozen=True)
class SeedRead:
    rows: Sequence[SeedRow]
    # Records of this scope that were read, even those with nothing in them.
    records: int


class SeedSourcePort(Protocol):
    async def read(self, obj: AttioObject) -> SeedRead:
        """The engine's fields as the object holds them, with the live Company or Person value
        as the baseline where there is one. Rows only for fields with something in them."""
        ...
