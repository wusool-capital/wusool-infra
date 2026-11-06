from datetime import UTC, datetime, timedelta

from app.modules.google_workspace import Attendee, CalendarPage, MailPage
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
from app.modules.interactions.tests.fakes.touches import JULES, NOW, SARA

LAST_SYNC = NOW - timedelta(days=10)
FINISHED = datetime(2026, 10, 1, tzinfo=UTC)
FULL_WINDOW = (months_before(NOW, 12), NOW + timedelta(days=180))
RECENT_WINDOW = (NOW - timedelta(days=7), NOW + timedelta(days=180))
# From where the window ended at the last sync (minus a day) to where it ends now.
HORIZON_SLICE = (LAST_SYNC + timedelta(days=179), NOW + timedelta(days=180))


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
    # Besides the changes, only the slice that just came inside the window is read.
    assert calendar.windows == [HORIZON_SLICE]
    *saved_pages, last = _calendar_batches(store)
    # The sync position moves once, at the very end, after every read above has worked.
    assert all(batch.cursor is None for batch in saved_pages)
    assert last.items == ()
    assert last.cursor is not None
    assert last.cursor.cursor == "sync-10"
    assert [i.source_id for i in store.items] == ["e2", "e3"]


async def test_each_poll_also_reads_the_slice_that_just_came_inside_the_window() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    # Nobody edited this meeting, so Google's changes list never mentions it.
    calendar.backfill_pages = [CalendarPage((event("edge", days_from_now=175),), None, None)]
    calendar.change_pages = [CalendarPage((), None, "sync-10")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert calendar.windows == [HORIZON_SLICE]
    assert [i.source_id for i in store.items] == ["edge"]


async def test_the_slice_starts_where_the_last_sync_left_off_however_long_ago() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    thirty_days_ago = NOW - timedelta(days=30)
    store.seed(SyncCursor(JULES, Source.CALENDAR, "sync-9", None, FINISHED, thirty_days_ago))
    calendar.change_pages = [CalendarPage((), None, "sync-10")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert calendar.windows == [(thirty_days_ago + timedelta(days=179), NOW + timedelta(days=180))]


async def test_a_slice_with_several_pages_is_read_to_the_end() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    calendar.backfill_pages = [
        CalendarPage((event("a", days_from_now=172),), "more", None),
        CalendarPage((event("b", days_from_now=174),), None, None),
    ]
    calendar.change_pages = [CalendarPage((), None, "sync-10")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert [i.source_id for i in store.items] == ["a", "b"]


async def test_a_failed_slice_leaves_the_sync_position_where_it_was() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    calendar.fail_backfill = True
    calendar.change_pages = [CalendarPage((event("e2"),), None, "sync-10")]

    report = await make_service(store, FakeMail(), calendar).run_pass()

    assert f"{JULES}:calendar" in report.failures
    cursor = _calendar_cursor(store)
    # Not advanced, so the next pass reads the same changes and the same slice again.
    assert (cursor.cursor, cursor.last_synced_at) == ("sync-9", LAST_SYNC)
    assert [i.source_id for i in store.items] == ["e2"]


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
    # A stored meeting that moved out of the window must stop counting, so it is hidden.
    assert sorted(store.cancelled) == ["far", "old"]


async def test_a_stored_meeting_the_team_member_then_declines_is_hidden() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    declined = (Attendee(JULES, "declined", True), Attendee(SARA, "accepted", False))
    calendar.change_pages = [CalendarPage((event("e1", attendees=declined),), None, "sync-10")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert store.items == []
    assert store.cancelled == ["e1"]


async def test_an_all_day_update_of_a_stored_meeting_hides_it() -> None:
    store, calendar = FakeStore(), FakeCalendar()
    _seed_calendar(store)
    calendar.change_pages = [CalendarPage((event("e1", all_day=True),), None, "sync-10")]

    await make_service(store, FakeMail(), calendar).run_pass()

    assert store.cancelled == ["e1"]


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
