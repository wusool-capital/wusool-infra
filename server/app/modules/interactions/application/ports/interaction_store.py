"""Where fetched interactions and their sync positions are kept.

Every method is its own transaction, so a page of rows and the cursor that
says "this page is done" are saved together or not at all.
"""

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from app.modules.interactions.domain.model import Channel, Direction, Role


class Source(StrEnum):
    GMAIL = "gmail"
    CALENDAR = "calendar"


@dataclass(frozen=True)
class NewParticipant:
    email: str
    domain: str
    role: Role


@dataclass(frozen=True)
class NewInteraction:
    mailbox: str
    channel: Channel
    source_id: str
    dedupe_key: str
    occurred_at: datetime
    direction: Direction | None
    thread_id: str | None
    subject: str | None
    participants: tuple[NewParticipant, ...]


@dataclass(frozen=True)
class SyncCursor:
    """Where one mailbox's Gmail or Calendar sync stands."""

    mailbox: str
    source: Source
    # Gmail history id or Calendar sync token.
    cursor: str | None
    backfill_page_token: str | None
    backfill_completed_at: datetime | None
    last_synced_at: datetime | None
    # Set by the store; anchors the backfill window so a resumed page token stays valid.
    created_at: datetime | None = None


@dataclass(frozen=True)
class PageBatch:
    mailbox: str
    source: Source
    items: tuple[NewInteraction, ...]
    # Meetings Google reports as cancelled, by event id.
    cancelled_source_ids: tuple[str, ...]
    # None leaves the saved cursor as it is.
    cursor: SyncCursor | None


@dataclass(frozen=True)
class AddressLink:
    email: str
    person_id: str | None
    organization_id: str | None


class InteractionStorePort(Protocol):
    async def read_cursor(self, mailbox: str, source: Source) -> SyncCursor | None: ...

    async def save_page(self, batch: PageBatch) -> int:
        """Rows written. A re-read email is skipped; a re-read meeting is updated in place."""
        ...

    async def unlinked_addresses(self, internal_domains: tuple[str, ...]) -> tuple[str, ...]:
        """Outside addresses with no Person or no Organization linked yet."""
        ...

    async def set_links(self, links: Sequence[AddressLink]) -> int:
        """Fills links in; never overwrites one that is already set."""
        ...

    async def purge_before(self, cutoff: datetime) -> int:
        """Deletes interactions that happened before `cutoff`; their participants go too."""
        ...
