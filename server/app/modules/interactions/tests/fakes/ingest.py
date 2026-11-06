"""In-memory stand-ins for the ports `IngestService` talks to, plus builders for fetched data."""

from collections.abc import Sequence
from dataclasses import replace
from datetime import UTC, date, datetime, timedelta

from app.modules.google_workspace import (
    Attendee,
    CalendarEvent,
    CalendarPage,
    CursorExpired,
    MailMessage,
    MailPage,
)
from app.modules.interactions.application.ingest import IngestConfig, IngestService
from app.modules.interactions.application.ports.interaction_store import (
    AddressLink,
    NewInteraction,
    PageBatch,
    Source,
    SyncCursor,
)
from app.modules.interactions.domain.linking import RecordDirectory
from app.modules.interactions.tests.fakes.touches import JULES, NOW, SARA

# What the database stamps on a cursor row the first time it is saved.
CREATED_AT = datetime(2026, 11, 5, 9, 0, tzinfo=UTC)
INTERNAL = ("wusoolcapital.com", "dopaminecap.com")

CONFIG = IngestConfig(
    mailboxes=(JULES,),
    internal_domains=INTERNAL,
    backfill_months=12,
    retention_months=12,
    next_window_days=180,
)


class FakeStore:
    def __init__(self) -> None:
        self.cursors: dict[tuple[str, Source], SyncCursor] = {}
        self.batches: list[PageBatch] = []
        self.items: list[NewInteraction] = []
        self.cancelled: list[str] = []
        self.links: dict[str, AddressLink] = {}
        self.purged_before: datetime | None = None

    async def read_cursor(self, mailbox: str, source: Source) -> SyncCursor | None:
        return self.cursors.get((mailbox, source))

    async def save_page(self, batch: PageBatch) -> int:
        self.batches.append(batch)
        self.items.extend(batch.items)
        self.cancelled.extend(batch.cancelled_source_ids)
        if batch.cursor is not None:
            key = (batch.mailbox, batch.source)
            existing = self.cursors.get(key)
            created = existing.created_at if existing else CREATED_AT
            self.cursors[key] = replace(batch.cursor, created_at=created)
        return len(batch.items)

    async def unlinked_addresses(self, internal_domains: tuple[str, ...]) -> tuple[str, ...]:
        seen = {
            p.email
            for item in self.items
            for p in item.participants
            if p.domain not in internal_domains and p.email not in self.links
        }
        return tuple(sorted(seen))

    async def set_links(self, links: Sequence[AddressLink]) -> int:
        self.links.update({link.email: link for link in links})
        return len(links)

    async def purge_before(self, cutoff: datetime) -> int:
        self.purged_before = cutoff
        return 0

    def seed(self, cursor: SyncCursor) -> None:
        self.cursors[(cursor.mailbox, cursor.source)] = replace(cursor, created_at=CREATED_AT)


class FakeDirectory:
    def __init__(self, directory: RecordDirectory | None = None, *, fails: bool = False) -> None:
        self._directory = directory or RecordDirectory({}, {})
        self._fails = fails
        self.loads = 0

    async def load(self) -> RecordDirectory:
        self.loads += 1
        if self._fails:
            raise RuntimeError("directory is down")
        return self._directory


class FakeMail:
    """Serves scripted pages and records what was asked for."""

    def __init__(self) -> None:
        self.history_id = "h100"
        self.backfill_pages: list[MailPage] = [MailPage((), None)]
        self.change_pages: list[MailPage] = []
        self.expire_changes = False
        self.fail_for: set[str] = set()
        self.calls: list[tuple[str, str | date | None]] = []

    async def current_history_id(self, mailbox: str) -> str:
        if mailbox in self.fail_for:
            raise RuntimeError("mail is down")
        self.calls.append(("current", mailbox))
        return self.history_id

    async def backfill_page(self, mailbox: str, since: date, page_token: str | None) -> MailPage:
        self.calls.append(("backfill", since))
        self.calls.append(("backfill-token", page_token))
        return self.backfill_pages.pop(0)

    async def changes_page(
        self, mailbox: str, start_history_id: str, page_token: str | None
    ) -> MailPage:
        self.calls.append(("changes", start_history_id))
        if self.expire_changes:
            self.expire_changes = False
            raise CursorExpired("gone")
        return self.change_pages.pop(0)


class FakeCalendar:
    def __init__(self) -> None:
        self.backfill_pages: list[CalendarPage] = [CalendarPage((), None, "sync-1")]
        self.change_pages: list[CalendarPage] = []
        self.expire_changes = False
        self.windows: list[tuple[datetime, datetime]] = []
        self.sync_tokens_used: list[str] = []

    async def backfill_page(
        self, mailbox: str, time_min: datetime, time_max: datetime, page_token: str | None
    ) -> CalendarPage:
        self.windows.append((time_min, time_max))
        return self.backfill_pages.pop(0)

    async def changes_page(
        self, mailbox: str, sync_token: str, page_token: str | None
    ) -> CalendarPage:
        self.sync_tokens_used.append(sync_token)
        if self.expire_changes:
            self.expire_changes = False
            raise CursorExpired("gone")
        return self.change_pages.pop(0)


def make_service(
    store: FakeStore,
    mail: FakeMail | None = None,
    calendar: FakeCalendar | None = None,
    directory: FakeDirectory | None = None,
    config: IngestConfig = CONFIG,
) -> IngestService:
    return IngestService(
        store,
        directory or FakeDirectory(),
        mail or FakeMail(),
        calendar or FakeCalendar(),
        config,
        clock=lambda: NOW,
    )


def message(
    source_id: str = "m1",
    *,
    sender: str | None = SARA,
    to: tuple[str, ...] = (JULES,),
    cc: tuple[str, ...] = (),
    days_ago: float = 1.0,
    subject: str | None = "Hello",
    labels: frozenset[str] = frozenset({"INBOX"}),
    message_id: str | None = "default",
) -> MailMessage:
    return MailMessage(
        source_id=source_id,
        thread_id=f"t-{source_id}",
        message_id=f"<{source_id}@mail>" if message_id == "default" else message_id,
        occurred_at=NOW - timedelta(days=days_ago),
        labels=labels,
        subject=subject,
        from_address=sender,
        to_addresses=to,
        cc_addresses=cc,
        auto_submitted=None,
        has_list_unsubscribe=False,
    )


def event(
    source_id: str = "e1",
    *,
    days_from_now: float = 3.0,
    attendees: tuple[Attendee, ...] | None = None,
    organizer: str | None = SARA,
    cancelled: bool = False,
    all_day: bool = False,
    subject: str | None = "Board call",
) -> CalendarEvent:
    guests = (
        attendees
        if attendees is not None
        else (Attendee(JULES, "accepted", True), Attendee(SARA, "accepted", False))
    )
    return CalendarEvent(
        source_id=source_id,
        cancelled=cancelled,
        ical_uid=f"{source_id}@google.com",
        starts_at=NOW + timedelta(days=days_from_now),
        all_day=all_day,
        subject=subject,
        organizer=organizer,
        attendees=guests,
    )
