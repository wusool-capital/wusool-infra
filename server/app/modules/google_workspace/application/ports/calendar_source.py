"""Reads Google Calendar events for one mailbox's primary calendar."""

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol

from app.modules.google_workspace.domain.model import CalendarEvent


@dataclass(frozen=True)
class CalendarPage:
    events: tuple[CalendarEvent, ...]
    next_page_token: str | None
    # Only on the last page, and only if Google issues one for the request.
    next_sync_token: str | None = None


class CalendarSourcePort(Protocol):
    async def backfill_page(
        self, mailbox: str, time_min: datetime, time_max: datetime, page_token: str | None
    ) -> CalendarPage: ...

    async def changes_page(
        self, mailbox: str, sync_token: str, page_token: str | None
    ) -> CalendarPage:
        """Raises `CursorExpired` when `sync_token` is no longer valid."""
        ...
