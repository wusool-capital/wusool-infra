"""Reads Gmail message metadata for one mailbox."""

from dataclasses import dataclass
from datetime import date
from typing import Protocol

from app.modules.interactions.domain.model import MailMessage


@dataclass(frozen=True)
class MailPage:
    messages: tuple[MailMessage, ...]
    next_page_token: str | None
    # Set on change pages: the bookmark to save once every page has been read.
    history_id: str | None = None


class MailSourcePort(Protocol):
    async def current_history_id(self, mailbox: str) -> str:
        """The change bookmark to record before a backfill starts."""
        ...

    async def backfill_page(
        self, mailbox: str, since: date, page_token: str | None
    ) -> MailPage: ...

    async def changes_page(
        self, mailbox: str, start_history_id: str, page_token: str | None
    ) -> MailPage:
        """Raises `CursorExpired` when `start_history_id` is too old."""
        ...
