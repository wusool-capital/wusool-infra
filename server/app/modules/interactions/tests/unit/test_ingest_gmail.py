from datetime import UTC, date, datetime, timedelta

from app.modules.google_workspace import MailPage
from app.modules.interactions.application.ports.interaction_store import (
    PageBatch,
    Source,
    SyncCursor,
)
from app.modules.interactions.domain.model import Direction
from app.modules.interactions.tests.fakes.ingest import (
    FakeMail,
    FakeStore,
    make_service,
    message,
)
from app.modules.interactions.tests.fakes.touches import JULES, NOW, RAMZY, SARA

LAST_SYNC = NOW - timedelta(days=10)
FINISHED = datetime(2026, 10, 1, tzinfo=UTC)


def _gmail_batches(store: FakeStore) -> list[PageBatch]:
    return [b for b in store.batches if b.source is Source.GMAIL]


def _gmail_cursor(store: FakeStore) -> SyncCursor:
    return store.cursors[(JULES, Source.GMAIL)]


def _seed_gmail(store: FakeStore, **overrides: str | datetime | None) -> None:
    fields = {
        "cursor": "h100",
        "backfill_page_token": None,
        "backfill_completed_at": FINISHED,
        "last_synced_at": LAST_SYNC,
    }
    fields.update(overrides)
    store.seed(SyncCursor(JULES, Source.GMAIL, **fields))  # type: ignore[arg-type]


async def test_the_first_pass_records_the_bookmark_before_it_reads_anything() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1"),), "p2"), MailPage((message("m2"),), None)]

    await make_service(store, mail).run_pass()

    assert mail.calls[0] == ("current", JULES)
    first = _gmail_batches(store)[0]
    assert first.items == ()
    assert first.cursor is not None
    assert first.cursor.cursor == "h100"
    assert [i.source_id for i in store.items] == ["m1", "m2"]


async def test_the_backfill_walks_every_page_then_marks_the_mailbox_done() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1"),), "p2"), MailPage((message("m2"),), None)]

    await make_service(store, mail).run_pass()

    tokens = [value for kind, value in mail.calls if kind == "backfill-token"]
    assert tokens == [None, "p2"]
    cursor = _gmail_cursor(store)
    assert (cursor.cursor, cursor.backfill_page_token) == ("h100", None)
    assert cursor.backfill_completed_at == NOW
    assert cursor.last_synced_at == NOW


async def test_each_backfill_page_saves_its_rows_and_its_place_together() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [MailPage((message("m1"),), "p2"), MailPage((message("m2"),), None)]

    await make_service(store, mail).run_pass()

    pages = [b for b in _gmail_batches(store) if b.items]
    assert [b.cursor.backfill_page_token for b in pages if b.cursor] == ["p2", None]


async def test_the_backfill_window_is_a_year_back_from_when_the_mailbox_was_first_seen() -> None:
    store, mail = FakeStore(), FakeMail()

    await make_service(store, mail).run_pass()

    assert ("backfill", date(2025, 11, 5)) in mail.calls


async def test_an_interrupted_backfill_resumes_from_its_saved_page() -> None:
    store, mail = FakeStore(), FakeMail()
    _seed_gmail(store, backfill_page_token="p2", backfill_completed_at=None, last_synced_at=None)
    mail.backfill_pages = [MailPage((message("m2"),), None)]

    await make_service(store, mail).run_pass()

    assert ("current", JULES) not in mail.calls
    assert ("backfill-token", "p2") in mail.calls
    assert ("backfill", date(2025, 11, 5)) in mail.calls
    assert _gmail_cursor(store).backfill_completed_at == NOW


async def test_a_finished_mailbox_polls_for_changes_and_moves_the_bookmark_on_the_last_page() -> (
    None
):
    store, mail = FakeStore(), FakeMail()
    _seed_gmail(store)
    mail.change_pages = [
        MailPage((message("m3"),), "more", "h150"),
        MailPage((message("m4"),), None, "h200"),
    ]

    await make_service(store, mail).run_pass()

    assert [c for c in mail.calls if c[0] == "changes"] == [("changes", "h100")] * 2
    first, last = _gmail_batches(store)
    assert first.cursor is None
    assert last.cursor is not None
    assert last.cursor.cursor == "h200"
    assert _gmail_cursor(store).last_synced_at == NOW
    assert [i.source_id for i in store.items] == ["m3", "m4"]


async def test_a_quiet_poll_still_advances_the_bookmark() -> None:
    store, mail = FakeStore(), FakeMail()
    _seed_gmail(store)
    mail.change_pages = [MailPage((), None, "h101")]

    await make_service(store, mail).run_pass()

    assert _gmail_cursor(store).cursor == "h101"


async def test_an_expired_bookmark_re_reads_from_the_last_sync_minus_a_day() -> None:
    store, mail = FakeStore(), FakeMail()
    _seed_gmail(store)
    mail.expire_changes = True
    mail.history_id = "h900"
    mail.backfill_pages = [MailPage((message("m5"),), None)]

    await make_service(store, mail).run_pass()

    since = (LAST_SYNC - timedelta(days=1)).date()
    assert [c for c in mail.calls if c[0] in ("changes", "current", "backfill")] == [
        ("changes", "h100"),
        ("current", JULES),
        ("backfill", since),
    ]
    cursor = _gmail_cursor(store)
    assert (cursor.cursor, cursor.backfill_completed_at, cursor.last_synced_at) == (
        "h900",
        NOW,
        NOW,
    )
    assert [i.source_id for i in store.items] == ["m5"]


async def test_recovery_takes_its_new_bookmark_before_it_re_reads() -> None:
    store, mail = FakeStore(), FakeMail()
    _seed_gmail(store)
    mail.expire_changes = True
    mail.history_id = "h900"

    await make_service(store, mail).run_pass()

    reset = next(b for b in _gmail_batches(store) if b.cursor and b.cursor.cursor == "h900")
    assert reset.items == ()
    assert reset.cursor is not None
    assert reset.cursor.backfill_completed_at is None


async def test_a_finished_mailbox_with_no_bookmark_is_recovered_not_polled() -> None:
    store, mail = FakeStore(), FakeMail()
    _seed_gmail(store, cursor=None)

    await make_service(store, mail).run_pass()

    assert not [c for c in mail.calls if c[0] == "changes"]
    assert ("current", JULES) in mail.calls
    assert _gmail_cursor(store).cursor == "h100"


async def test_only_real_conversations_inside_the_retention_window_are_stored() -> None:
    store, mail = FakeStore(), FakeMail()
    mail.backfill_pages = [
        MailPage(
            (
                message("kept"),
                message("sent", sender=JULES, to=(SARA,)),
                message("internal", sender=RAMZY, to=(JULES,)),
                message("spam", labels=frozenset({"SPAM"})),
                message("ancient", days_ago=400),
            ),
            None,
        )
    ]

    await make_service(store, mail).run_pass()

    assert [i.source_id for i in store.items] == ["kept", "sent"]
    assert [i.direction for i in store.items] == [Direction.INBOUND, Direction.OUTBOUND]
