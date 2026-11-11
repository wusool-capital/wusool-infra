"""Stored interactions, shaped as the touches that scoring reads."""

from collections.abc import Mapping
from typing import Protocol

from app.modules.interactions.domain.model import Touch


class TouchReaderPort(Protocol):
    async def touches_by_organization(self) -> Mapping[str, tuple[Touch, ...]]:
        """Touches per Organization id, cancelled meetings left out."""
        ...
