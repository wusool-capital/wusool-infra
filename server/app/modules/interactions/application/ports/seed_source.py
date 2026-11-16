"""What Attio holds today, read once before the engine writes anything."""

from collections.abc import Sequence
from typing import Protocol

from app.modules.interactions.application.ports.sent_values import SeedRow
from app.modules.interactions.domain.attio_fields import AttioObject


class SeedSourcePort(Protocol):
    async def rows(self, obj: AttioObject) -> Sequence[SeedRow]:
        """The engine's fields as the Organizations or Person hold them, with the live
        Company or Person value as the baseline. Only fields with something in them."""
        ...
