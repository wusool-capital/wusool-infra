"""Writing computed fields onto an Attio record."""

from collections.abc import Sequence
from typing import Protocol

from app.modules.interactions.domain.attio_fields import AttioObject, FieldValue


class WritesNotAllowedError(RuntimeError):
    """Raised instead of writing while the instance is flagged as test (`ATTIO_IS_TEST`)."""


class RecordGoneError(RuntimeError):
    """Raised when Attio no longer has the record, for example after a merge or delete."""


class AttioWriterPort(Protocol):
    async def patch(self, obj: AttioObject, record_id: str, fields: Sequence[FieldValue]) -> None:
        """Send only these fields. Attio is written first; the caller records it afterwards."""
        ...
