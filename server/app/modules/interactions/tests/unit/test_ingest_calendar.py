from datetime import UTC, datetime, timedelta

from app.modules.google_workspace import CalendarPage, MailPage
from app.modules.interactions.application.ports.interaction_store import (
    PageBatch,
    Source,
    SyncCursor,
)
from app.modules.interactions.domain.windows import months_before
from app.modules.interactions.tests.fakes.ingest import (
    FakeCalendar,
    FakeMail,
    FakeStore,
    event,
    make_service,
)
from app.modules.interactions.tests.fakes.touches import JULES, NOW

LAST_SYNC = NOW - timedelta(days=10)
FINISHED = datetime(2026, 10, 1, tzinfo=UTC)
FULL_WINDOW = (months_before(NOW, 12), NOW + timedelta(days=180))
RECENT_WINDOW = (NOW - timedelta(days=7), NOW + timedelta(days=180))


def _calendar_batches(store: FakeStore) -> list[PageBatch]:
    return [b for b in store.batches if b.source is Source.CALENDAR]


def _calendar_cursor(store: FakeStore) -> SyncCursor:
    return store.cursors[(JULES, Source.CALENDAR)]


def _seed_calendar(store: FakeStore, token: str | None = "sync-9") -> None:
    store.seed(SyncCursor(JULES, Source.CALENDAR, token, None, FINISHED, LAST_SYNC))


async def test_the_first_read_covers_a_year_back_to_six_months_ahead_and_keeps_the_token() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    calendar.backfill_pages = [
        CalendarPage((event("e1"), event("gone", cancelled=True)), None, "sync-9")
    ]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert calendar.windows == [FULL_WINDOW]
    assert [i.source_id for i in store.items] == ["e1"]
    assert store.cancelled == ["gone"]
    cursor = _calendar_cursor(store)
    assert (cursor.cursor, cursor.backfill_completed_at, cursor.last_synced_at) == (
        "sync-9",
        NOW,
        NOW,
    )


async def test_later_passes_ask_only_for_changes_since_the_token() -> None:
    store, calendar, mail = FakeStore(), FakeCalendar(), FakeMail()
    _seed_calendar(store)
    mail.backfill_pages = [MailPage((), None)]
    calendar.change_pages = [
        CalendarPage((event("e2"),), "more", None),
        CalendarPage((event("e3"),), None, "sync-10"),
    ]

    await make_service(store, mail, calendar).run_pass()

    assert calendar.sync_tokens_used == ["sync-9", "sync-9"]
    assert calendar.windows == []
    first, last = _calendar_batches(store)
    assert first.cursor is None
    assert last.cursor is not None
    assert last.cursor.cursor == "sync-10"
    assert [i.source_id for i in store.items] == ["e2", "e3"]


async def test_changes_to_events_outside_the_kept_window_are_dropped() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    calendar.change_pages = [
        CalendarPage(
            (
                event("near"),
                event("far", days_from_now=200),
                event("old", days_from_now=-400),
            ),
            None,
            "sync-10",
        )
    ]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert [i.source_id for i in store.items] == ["near"]


async def test_a_cancelled_meeting_is_reported_even_when_its_date_is_unknown() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    calendar.change_pages = [CalendarPage((event("e1", cancelled=True),), None, "sync-10")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert store.items == []
    assert store.cancelled == ["e1"]


async def test_an_expired_token_triggers_a_full_re_read_and_a_fresh_token() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    calendar.expire_changes = True
    calendar.backfill_pages = [CalendarPage((event("e4"),), None, "sync-11")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert calendar.windows == [FULL_WINDOW]
    assert _calendar_cursor(store).cursor == "sync-11"
    assert [i.source_id for i in store.items] == ["e4"]


async def test_without_a_sync_token_each_pass_re_reads_the_recent_window() -> None:
    store, calendar, mail = FakeStore(), FakeCalendar(), FakeMail()
    calendar.backfill_pages = [
        CalendarPage((event("e1"),), None, None),
        CalendarPage((event("e5"),), None, None),
    ]

    service = make_service(store, mail, calendar)
    await service.run_pass()
    mail.change_pages = [MailPage((), None, "h101")]
    await service.run_pass()

    assert calendar.windows == [FULL_WINDOW, RECENT_WINDOW]
    cursor = _calendar_cursor(store)
    assert cursor.cursor is None
    assert cursor.backfill_completed_at == NOW
    assert [i.source_id for i in store.items] == ["e1", "e5"]
