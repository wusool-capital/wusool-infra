"""The persistence interface for the raw Attio delivery log
(`attio_raw_events`) — implemented by `persistence/raw_events.py`. Both calls
are best-effort: the log exists for replay and debugging, so a failure to
write it must never stop an event being synced."""

from typing import Protocol
from uuid import UUID


class RawEventLogPort(Protocol):
    async def record(self, *, event_type: str, payload_json: str) -> UUID | None:
        """Returns the new row's id, or None when it could not be written."""
        ...

    async def mark_processed(self, raw_event_id: UUID) -> None: ...
