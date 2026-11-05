from datetime import UTC, datetime, timedelta, timezone

import httpx
import pytest

from app.modules.interactions.application.errors import CursorExpired
from app.modules.interactions.domain.model import Attendee
from app.modules.interactions.providers.google.calendar import CalendarClient
from app.modules.interactions.providers.google.http import GoogleApiError
from app.modules.interactions.tests.fakes.google import (
    RecordedSleeps,
    StaticTokenSource,
    http_client,
)

MAILBOX = "jules@wusoolcapital.com"
TIME_MIN = datetime(2025, 11, 5, tzinfo=UTC)
TIME_MAX = TIME_MIN + timedelta(days=545)


class _Calendar:
    def __init__(self, response: httpx.Response) -> None:
        self.response = response
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        return self.response


def _timed(event_id: str) -> dict[str, str | dict[str, str]]:
    """A confirmed, timed event; tests merge in whatever they want to vary."""
    return {
        "id": event_id,
        "status": "confirmed",
        "iCalUID": f"{event_id}@google.com",
        "summary": "Board call",
        "start": {"dateTime": "2026-11-10T14:00:00+04:00"},
    }


async def _backfill(calendar: _Calendar, page_token: str | None = None):
    async with http_client(calendar) as http:
        client = CalendarClient(http, StaticTokenSource(), RecordedSleeps())
        return await client.backfill_page(MAILBOX, TIME_MIN, TIME_MAX, page_token)


async def test_backfill_bounds_the_window_and_expands_recurring_events() -> None:
    calendar = _Calendar(httpx.Response(200, json={"items": []}))

    await _backfill(calendar, "p2")

    params = calendar.requests[0].url.params
    assert calendar.requests[0].url.path == "/calendar/v3/calendars/primary/events"
    assert params["singleEvents"] == "true"
    assert params["showDeleted"] == "true"
    assert params["timeMin"] == "2025-11-05T00:00:00+00:00"
    assert params["timeMax"] == TIME_MAX.isoformat()
    assert params["pageToken"] == "p2"
    assert "syncToken" not in params


async def test_a_timed_event_maps_its_attendees_and_the_self_response() -> None:
    event = _timed("e1") | {
        "organizer": {"email": "Sara@Acme.com"},
        "attendees": [
            {"email": "sara@acme.com", "responseStatus": "accepted"},
            {"email": "Jules@WusoolCapital.com", "responseStatus": "declined", "self": True},
            {"displayName": "Room 4"},
        ],
    }
    calendar = _Calendar(httpx.Response(200, json={"items": [event], "nextPageToken": "n"}))

    page = await _backfill(calendar)

    (mapped,) = page.events
    assert page.next_page_token == "n"
    assert mapped.source_id == "e1"
    assert mapped.ical_uid == "e1@google.com"
    assert mapped.starts_at == datetime(2026, 11, 10, 14, tzinfo=timezone(timedelta(hours=4)))
    assert (mapped.all_day, mapped.cancelled, mapped.subject) == (False, False, "Board call")
    assert mapped.organizer == "sara@acme.com"
    assert mapped.attendees == (
        Attendee("sara@acme.com", "accepted", False),
        Attendee("jules@wusoolcapital.com", "declined", True),
    )


async def test_an_all_day_event_is_flagged_and_starts_at_utc_midnight() -> None:
    event = _timed("e2") | {"start": {"date": "2026-11-12"}}

    page = await _backfill(_Calendar(httpx.Response(200, json={"items": [event]})))

    assert page.events[0].all_day is True
    assert page.events[0].starts_at == datetime(2026, 11, 12, tzinfo=UTC)


async def test_a_cancelled_event_may_carry_nothing_but_its_id() -> None:
    page = await _backfill(
        _Calendar(httpx.Response(200, json={"items": [{"id": "e3", "status": "cancelled"}]}))
    )

    (mapped,) = page.events
    assert (mapped.source_id, mapped.cancelled) == ("e3", True)
    assert (mapped.ical_uid, mapped.starts_at, mapped.attendees) == (None, None, ())


async def test_a_live_event_that_cannot_be_keyed_is_dropped() -> None:
    items = [
        _timed("no-uid") | {"iCalUID": None},
        _timed("no-start") | {"start": None},
        {"id": "empty-start", "status": "confirmed", "iCalUID": "u", "start": {}},
        _timed("ok"),
    ]

    page = await _backfill(_Calendar(httpx.Response(200, json={"items": items})))

    assert [e.source_id for e in page.events] == ["ok"]


async def test_the_sync_token_is_passed_back_on_the_last_page() -> None:
    page = await _backfill(
        _Calendar(httpx.Response(200, json={"items": [], "nextSyncToken": "sync-1"}))
    )

    assert (page.next_page_token, page.next_sync_token) == (None, "sync-1")


async def test_a_page_without_a_sync_token_leaves_it_empty() -> None:
    page = await _backfill(_Calendar(httpx.Response(200, json={"items": []})))

    assert page.next_sync_token is None


async def test_changes_send_the_sync_token_and_no_time_window() -> None:
    calendar = _Calendar(httpx.Response(200, json={"items": [], "nextSyncToken": "sync-2"}))

    async with http_client(calendar) as http:
        page = await CalendarClient(http, StaticTokenSource(), RecordedSleeps()).changes_page(
            MAILBOX, "sync-1", None
        )

    params = calendar.requests[0].url.params
    assert params["syncToken"] == "sync-1"
    assert params["showDeleted"] == "true"
    assert "timeMin" not in params
    assert "timeMax" not in params
    assert page.next_sync_token == "sync-2"


async def test_an_expired_sync_token_raises_cursor_expired() -> None:
    async with http_client(_Calendar(httpx.Response(410))) as http:
        client = CalendarClient(http, StaticTokenSource(), RecordedSleeps())
        with pytest.raises(CursorExpired):
            await client.changes_page(MAILBOX, "old", None)


async def test_any_other_calendar_failure_is_not_mistaken_for_an_expired_token() -> None:
    async with http_client(_Calendar(httpx.Response(403, json={"error": "forbidden"}))) as http:
        client = CalendarClient(http, StaticTokenSource(), RecordedSleeps())
        with pytest.raises(GoogleApiError) as caught:
            await client.changes_page(MAILBOX, "tok", None)

    assert caught.value.status == 403
