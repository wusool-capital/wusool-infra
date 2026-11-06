"""The CRM records an address can be linked to."""

from typing import Protocol

from app.modules.interactions.domain.linking import RecordDirectory


class RecordDirectoryPort(Protocol):
    async def load(self) -> RecordDirectory:
        """Every live Person and Organization. Cheap enough to reload on each pass."""
        ...
