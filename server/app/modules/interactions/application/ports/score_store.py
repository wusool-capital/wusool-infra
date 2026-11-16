"""The numeric score behind each record's connection strength, kept only in Postgres."""

from collections.abc import Mapping
from decimal import Decimal
from typing import Protocol

from app.modules.interactions.domain.attio_fields import AttioObject


class ScoreStorePort(Protocol):
    async def load(self, obj: AttioObject) -> Mapping[str, Decimal | None]:
        """The stored score of every record the mirror holds; a record absent here is skipped."""
        ...

    async def save(self, obj: AttioObject, scores: Mapping[str, Decimal]) -> int:
        """Store these scores. Returns how many rows changed."""
        ...
