"""One ingest pass: read each mailbox's Gmail and Calendar, store it, link addresses.

Reads only. Nothing here writes to Attio.
"""

import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import UTC, datetime, timedelta

from app.modules.google_workspace import (
    CalendarEvent,
    CalendarSourcePort,
    CursorExpired,
    MailMessage,
    MailSourcePort,
)
from app.modules.interactions.application.mapping import email_to_item, event_to_item
from app.modules.interactions.application.ports.interaction_store import (
    AddressLink,
    InteractionStorePort,
    NewInteraction,
    PageBatch,
    Source,
    SyncCursor,
)
from app.modules.interactions.application.ports.record_directory import RecordDirectoryPort
from app.modules.interactions.domain.linking import Ambiguity, resolve_link
from app.modules.interactions.domain.windows import months_before

logger = logging.getLogger(__name__)

# Used only when Google issues no sync token: re-read this much recent calendar each pass.
_RECENT_CALENDAR_WINDOW = timedelta(days=7)


@dataclass(frozen=True)
class IngestConfig:
    mailboxes: tuple[str, ...]
    internal_domains: tuple[str, ...]
    backfill_months: int
    retention_months: int
    next_window_days: int


@dataclass(frozen=True)
class PassReport:
    written: int
    linked: int
    shared_emails: int
    shared_domains: int
    failures: tuple[str, ...]


def _utc_now() -> datetime:
    return datetime.now(UTC)


class IngestService:
    def __init__(
        self,
        store: InteractionStorePort,
        directory: RecordDirectoryPort,
        mail: MailSourcePort,
        calendar: CalendarSourcePort,
        config: IngestConfig,
        clock: Callable[[], datetime] = _utc_now,
    ) -> None:
        self._store = store
        self._directory = directory
        self._mail = mail
        self._calendar = calendar
        self._config = config
        self._clock = clock

    async def run_pass(self) -> PassReport:
        written = 0
        failures: list[str] = []
        for mailbox in self._config.mailboxes:
            for source, sync in (
                (Source.GMAIL, self._sync_gmail),
                (Source.CALENDAR, self._sync_calendar),
            ):
                try:
                    written += await sync(mailbox)
                except Exception:
                    # One failing mailbox must not stop the others; the next pass retries it.
                    logger.exception(
                        "interactions_sync_failed mailbox=%s source=%s", mailbox, source
                    )
                    failures.append(f"{mailbox}:{source}")
        linked = shared_emails = shared_domains = 0
        try:
            linked, shared_emails, shared_domains = await self._link_participants()
        except Exception:
            # Linking can be retried next pass; the rows it follows are already saved.
            logger.exception("interactions_link_failed")
            failures.append("linking")
        report = PassReport(written, linked, shared_emails, shared_domains, tuple(failures))
        logger.info(
            "interactions_pass written=%d linked=%d shared_emails=%d shared_domains=%d failures=%d",
            report.written,
            report.linked,
            report.shared_emails,
            report.shared_domains,
            len(report.failures),
        )
        return report

    async def purge_expired(self) -> int:
        cutoff = months_before(self._clock(), self._config.retention_months)
        return await self._store.purge_before(cutoff)

    # --- Gmail ---------------------------------------------------------------------------

    async def _sync_gmail(self, mailbox: str) -> int:
        cursor = await self._store.read_cursor(mailbox, Source.GMAIL)
        if cursor is None:
            # Bookmark first, so mail arriving mid-backfill is picked up by the first poll.
            bookmark = await self._mail.current_history_id(mailbox)
            cursor = await self._start(mailbox, Source.GMAIL, bookmark)
        now = self._clock()
        if cursor.backfill_completed_at is None:
            return await self._gmail_backfill(cursor, now)
        if cursor.cursor is None:
            return await self._gmail_recover(cursor, now)
        try:
            return await self._gmail_changes(cursor, cursor.cursor, now)
        except CursorExpired:
            logger.warning("interactions_gmail_bookmark_expired mailbox=%s", mailbox)
            return await self._gmail_recover(cursor, now)

    async def _gmail_backfill(self, cursor: SyncCursor, now: datetime) -> int:
        since = self._backfill_start(cursor, now).date()
        token = cursor.backfill_page_token
        written = 0
        while True:
            page = await self._mail.backfill_page(cursor.mailbox, since, token)
            token = page.next_page_token
            cursor = replace(cursor, backfill_page_token=token)
            if token is None:
                cursor = replace(cursor, backfill_completed_at=now, last_synced_at=now)
            items = self._email_items(cursor.mailbox, page.messages, now)
            written += await self._save(cursor.mailbox, Source.GMAIL, items, (), cursor)
            if token is None:
                return written

    async def _gmail_changes(self, cursor: SyncCursor, start_id: str, now: datetime) -> int:
        token: str | None = None
        written = 0
        while True:
            page = await self._mail.changes_page(cursor.mailbox, start_id, token)
            token = page.next_page_token
            # The bookmark moves only once every page of this poll has been saved.
            final = (
                replace(cursor, cursor=page.history_id or start_id, last_synced_at=now)
                if token is None
                else None
            )
            items = self._email_items(cursor.mailbox, page.messages, now)
            written += await self._save(cursor.mailbox, Source.GMAIL, items, (), final)
            if token is None:
                return written

    async def _gmail_recover(self, cursor: SyncCursor, now: datetime) -> int:
        """A dropped bookmark: re-read from the last sync, whatever the outage length."""
        bookmark = await self._mail.current_history_id(cursor.mailbox)
        reset = replace(
            cursor, cursor=bookmark, backfill_page_token=None, backfill_completed_at=None
        )
        await self._save(cursor.mailbox, Source.GMAIL, (), (), reset)
        return await self._gmail_backfill(reset, now)

    def _backfill_start(self, cursor: SyncCursor, now: datetime) -> datetime:
        """Stable across restarts, so a saved page token still matches its query."""
        if cursor.last_synced_at is not None:
            return cursor.last_synced_at - timedelta(days=1)
        return months_before(cursor.created_at or now, self._config.backfill_months)

    def _email_items(
        self, mailbox: str, messages: Sequence[MailMessage], now: datetime
    ) -> tuple[NewInteraction, ...]:
        earliest = months_before(now, self._config.retention_months)
        mapped = (email_to_item(mailbox, m, self._config.internal_domains) for m in messages)
        return tuple(i for i in mapped if i is not None and i.occurred_at >= earliest)

    # --- Calendar ------------------------------------------------------------------------

    async def _sync_calendar(self, mailbox: str) -> int:
        cursor = await self._store.read_cursor(mailbox, Source.CALENDAR)
        if cursor is None:
            cursor = await self._start(mailbox, Source.CALENDAR, None)
        now = self._clock()
        if cursor.backfill_completed_at is None:
            return await self._calendar_full(cursor, now)
        if cursor.cursor is None:
            return await self._calendar_read(cursor, now, now - _RECENT_CALENDAR_WINDOW, False)
        try:
            return await self._calendar_changes(cursor, cursor.cursor, now)
        except CursorExpired:
            logger.warning("interactions_calendar_sync_token_expired mailbox=%s", mailbox)
            return await self._calendar_full(cursor, now)

    async def _calendar_full(self, cursor: SyncCursor, now: datetime) -> int:
        time_min = months_before(now, self._config.backfill_months)
        return await self._calendar_read(cursor, now, time_min, True)

    async def _calendar_read(
        self, cursor: SyncCursor, now: datetime, time_min: datetime, fresh_sync: bool
    ) -> int:
        """Pages through a bounded window. A full read also records the sync token."""
        time_max = now + timedelta(days=self._config.next_window_days)
        token: str | None = None
        written = 0
        while True:
            page = await self._calendar.backfill_page(cursor.mailbox, time_min, time_max, token)
            token = page.next_page_token
            final = None
            if token is None:
                final = replace(cursor, last_synced_at=now)
                if fresh_sync:
                    final = replace(final, cursor=page.next_sync_token, backfill_completed_at=now)
                    if page.next_sync_token is None:
                        logger.warning(
                            "interactions_calendar_no_sync_token mailbox=%s", cursor.mailbox
                        )
            written += await self._save_events(cursor.mailbox, page.events, now, final)
            if token is None:
                return written

    async def _calendar_changes(self, cursor: SyncCursor, sync_token: str, now: datetime) -> int:
        token: str | None = None
        written = 0
        while True:
            page = await self._calendar.changes_page(cursor.mailbox, sync_token, token)
            token = page.next_page_token
            final = (
                replace(cursor, cursor=page.next_sync_token or sync_token, last_synced_at=now)
                if token is None
                else None
            )
            written += await self._save_events(cursor.mailbox, page.events, now, final)
            if token is None:
                return written

    async def _save_events(
        self,
        mailbox: str,
        events: Sequence[CalendarEvent],
        now: datetime,
        cursor: SyncCursor | None,
    ) -> int:
        # An incremental sync can't be limited by time, so keep only the window we store.
        earliest = months_before(now, self._config.retention_months)
        latest = now + timedelta(days=self._config.next_window_days)
        items: list[NewInteraction] = []
        cancelled: list[str] = []
        for event in events:
            if event.cancelled:
                cancelled.append(event.source_id)
                continue
            item = event_to_item(mailbox, event, self._config.internal_domains)
            if item is not None and earliest <= item.occurred_at <= latest:
                items.append(item)
            else:
                # We may already hold this meeting; a declined or moved-away one must stop counting.
                cancelled.append(event.source_id)
        return await self._save(mailbox, Source.CALENDAR, tuple(items), tuple(cancelled), cursor)

    # --- Shared --------------------------------------------------------------------------

    async def _start(self, mailbox: str, source: Source, cursor: str | None) -> SyncCursor:
        first = SyncCursor(mailbox, source, cursor, None, None, None)
        await self._store.save_page(PageBatch(mailbox, source, (), (), first))
        saved = await self._store.read_cursor(mailbox, source)
        if saved is None:
            raise RuntimeError(f"sync cursor for {mailbox} {source} was not saved")
        return saved

    async def _save(
        self,
        mailbox: str,
        source: Source,
        items: tuple[NewInteraction, ...],
        cancelled: tuple[str, ...],
        cursor: SyncCursor | None,
    ) -> int:
        return await self._store.save_page(PageBatch(mailbox, source, items, cancelled, cursor))

    async def _link_participants(self) -> tuple[int, int, int]:
        addresses = await self._store.unlinked_addresses(self._config.internal_domains)
        if not addresses:
            return 0, 0, 0
        directory = await self._directory.load()
        links: list[AddressLink] = []
        shared_emails = shared_domains = 0
        for address in addresses:
            resolution = resolve_link(address, directory)
            if resolution.ambiguity is Ambiguity.SHARED_EMAIL:
                shared_emails += 1
            elif resolution.ambiguity is Ambiguity.SHARED_DOMAIN:
                shared_domains += 1
            if resolution.person_id or resolution.organization_id:
                links.append(AddressLink(address, resolution.person_id, resolution.organization_id))
        return await self._store.set_links(links), shared_emails, shared_domains
