# How to read `google_workspace`

A walkthrough for someone who has never seen this module. It is small and has no
database, so read it top to bottom.

## The one-sentence version

Act as a mailbox via domain-wide delegation, then read that mailbox's Gmail
messages and Calendar events as typed data.

## Read in this order

1. `providers/google/auth.py`: `DelegatedTokenSource` signs a short-lived JWT
   naming the mailbox in `sub` and trades it at Google's token endpoint. Tokens
   are cached per mailbox until a minute before they expire.
2. `providers/google/http.py`: `get_model` is the one place a request is made.
   It adds the bearer token, retries transient failures, and parses the reply.
3. `providers/google/models.py`: the Pydantic shape of each reply. Only the
   fields we use are declared.
4. `providers/google/gmail.py` and `calendar.py`: they turn those models into
   the plain dataclasses in `domain/model.py`.
5. `application/ports/`: the Protocols a consumer types against and fakes.
6. `tests/unit/`: each client is tested with `httpx.MockTransport`, so nothing
   touches the network.

## Two things that are easy to miss

**Expired bookmarks are an error, not an empty result.** Gmail and Calendar
each hand back a bookmark to resume from. When Google no longer honours one, the
client raises `CursorExpired` and the consumer decides how far back to re-read.
This module never guesses.

**A cancelled event can be nearly empty.** It may carry only an id and a status.
`CalendarEvent` therefore has optional `ical_uid` and `starts_at`; a live event
missing either is dropped instead.

## Why `domain/` and `application/` import no framework

`tests/test_architecture.py` fails if either imports `pydantic`, `httpx`,
`fastapi`, `sqlalchemy` or `google`, or if anything here imports a consumer such
as `interactions`. Settings use pydantic, so they live in `config.py` at the
module root.
