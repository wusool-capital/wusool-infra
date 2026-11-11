"""Typed shapes of the Gmail and Calendar replies this module reads.

Only the fields we use are declared; Google may send more and those are
ignored. Parsing here keeps raw JSON from spreading into the application.
"""

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _Reply(BaseModel):
    model_config = ConfigDict(
        frozen=True, extra="ignore", alias_generator=to_camel, populate_by_name=True
    )


class GmailMessageRef(_Reply):
    id: str
    thread_id: str


class GmailList(_Reply):
    messages: list[GmailMessageRef] = Field(default_factory=list)
    next_page_token: str | None = None


class GmailHeader(_Reply):
    name: str
    value: str


class GmailPayload(_Reply):
    headers: list[GmailHeader] = Field(default_factory=list)


class GmailMessage(_Reply):
    id: str
    thread_id: str
    label_ids: list[str] = Field(default_factory=list)
    # Milliseconds since the epoch, as a string.
    internal_date: str
    payload: GmailPayload = Field(default_factory=GmailPayload)


class GmailProfile(_Reply):
    history_id: str


class GmailHistoryAdded(_Reply):
    message: GmailMessageRef


class GmailHistoryRecord(_Reply):
    messages_added: list[GmailHistoryAdded] = Field(default_factory=list)


class GmailHistory(_Reply):
    history: list[GmailHistoryRecord] = Field(default_factory=list)
    next_page_token: str | None = None
    history_id: str


class CalendarTime(_Reply):
    # `date` for an all-day event, `dateTime` for a timed one.
    date: str | None = None
    date_time: str | None = None


class CalendarPerson(_Reply):
    email: str | None = None


class CalendarAttendeeItem(_Reply):
    email: str | None = None
    response_status: str | None = None
    is_self: bool = Field(default=False, alias="self")
    resource: bool = False


class CalendarItem(_Reply):
    id: str
    status: str | None = None
    ical_uid: str | None = Field(default=None, alias="iCalUID")
    summary: str | None = None
    start: CalendarTime | None = None
    organizer: CalendarPerson | None = None
    attendees: list[CalendarAttendeeItem] = Field(default_factory=list)


class CalendarList(_Reply):
    items: list[CalendarItem] = Field(default_factory=list)
    next_page_token: str | None = None
    next_sync_token: str | None = None
