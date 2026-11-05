"""Google Calendar over HTTPS: the primary calendar's events for one mailbox."""

import asyncio
from datetime import UTC, date, datetime, time

import httpx

from app.modules.google_workspace.application.errors import CursorExpired
from app.modules.google_workspace.application.ports.calendar_source import CalendarPage
from app.modules.google_workspace.application.ports.token_source import TokenSource
from app.modules.google_workspace.domain.addresses import normalize_address
from app.modules.google_workspace.domain.model import Attendee, CalendarEvent
from app.modules.google_workspace.providers.google.http import GoogleApiError, Sleep, get_model
from app.modules.google_workspace.providers.google.models import (
    CalendarAttendeeItem,
    CalendarItem,
    CalendarList,
)

_URL = "https://www.googleapis.com/calendar/v3/calendars/primary/events"
_PAGE_SIZE = "250"
# Backfill and incremental requests share these, so a sync token stays valid for the next call.
_COMMON_PARAMS = [("singleEvents", "true"), ("showDeleted", "true"), ("maxResults", _PAGE_SIZE)]


class CalendarClient:
    def __init__(
        self, http: httpx.AsyncClient, tokens: TokenSource, sleep: Sleep = asyncio.sleep
    ) -> None:
        self._http = http
        self._tokens = tokens
        self._sleep = sleep

    async def backfill_page(
        self, mailbox: str, time_min: datetime, time_max: datetime, page_token: str | None
    ) -> CalendarPage:
        params = [
            *_COMMON_PARAMS,
            ("timeMin", time_min.isoformat()),
            ("timeMax", time_max.isoformat()),
            *_page_param(page_token),
        ]
        return await self._page(mailbox, params)

    async def changes_page(
        self, mailbox: str, sync_token: str, page_token: str | None
    ) -> CalendarPage:
        params = [*_COMMON_PARAMS, ("syncToken", sync_token), *_page_param(page_token)]
        try:
            return await self._page(mailbox, params)
        except GoogleApiError as error:
            if error.status == 410:
                raise CursorExpired(f"Calendar sync token expired for {mailbox}") from error
            raise

    async def _page(self, mailbox: str, params: list[tuple[str, str]]) -> CalendarPage:
        listing = await get_model(
            self._http, self._tokens, mailbox, _URL, params, CalendarList, self._sleep
        )
        events = (_to_event(item) for item in listing.items)
        return CalendarPage(
            events=tuple(event for event in events if event is not None),
            next_page_token=listing.next_page_token,
            next_sync_token=listing.next_sync_token,
        )


def _page_param(page_token: str | None) -> list[tuple[str, str]]:
    return [("pageToken", page_token)] if page_token else []


def _to_event(item: CalendarItem) -> CalendarEvent | None:
    cancelled = item.status == "cancelled"
    starts_at, all_day = _start_of(item)
    # A live event with no start or iCalUID can't be keyed; a cancelled one only needs its id.
    if not cancelled and (starts_at is None or item.ical_uid is None):
        return None
    return CalendarEvent(
        source_id=item.id,
        cancelled=cancelled,
        ical_uid=item.ical_uid,
        starts_at=starts_at,
        all_day=all_day,
        subject=item.summary,
        organizer=_address(item.organizer.email) if item.organizer else None,
        attendees=tuple(a for a in map(_to_attendee, item.attendees) if a is not None),
    )


def _start_of(item: CalendarItem) -> tuple[datetime | None, bool]:
    if item.start is None:
        return None, False
    if item.start.date_time:
        return datetime.fromisoformat(item.start.date_time), False
    if item.start.date:
        return datetime.combine(date.fromisoformat(item.start.date), time.min, tzinfo=UTC), True
    return None, False


def _to_attendee(item: CalendarAttendeeItem) -> Attendee | None:
    address = _address(item.email)
    if address is None:
        return None
    return Attendee(address=address, response_status=item.response_status, is_self=item.is_self)


def _address(raw: str | None) -> str | None:
    return normalize_address(raw) if raw else None
