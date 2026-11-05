# google_workspace

Read access to Gmail and Google Calendar through one service account with
domain-wide delegation. It gives consumers delegated tokens, typed Gmail and
Calendar clients, and the plain data those return. `interactions` is the first
consumer; Scribe's calendar logic is the next. It is its own module so a second
consumer never has to reach into the first one's code.

No `persistence/`, no `api/`, no `bootstrap.py`: this module owns no tables and
no HTTP surface. It imports nothing from its consumers.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Structure

```
google_workspace/
  __init__.py                    # the public facade: every name other modules may import
  config.py                      # GoogleWorkspaceSettings.google_service_account_json
  domain/
    model.py                     # MailMessage, CalendarEvent, Attendee
    addresses.py                 # normalize_address, parse_address_list
    scopes.py                    # GMAIL_READONLY, CALENDAR_READONLY
  application/
    errors.py                    # CursorExpired
    ports/                       # TokenSource, MailSourcePort, CalendarSourcePort (Protocols)
  providers/google/
    auth.py                      # ServiceAccountKey, DelegatedTokenSource
    http.py                      # one authenticated GET with retries, parsed into a model
    models.py                    # Pydantic shapes of the Gmail and Calendar replies
    gmail.py, calendar.py        # GmailClient, CalendarClient
```

## Public contract

Import only the names in `__init__.py`'s `__all__`. The repo's architecture
test enforces that. Consumers type against the ports and fake them in tests;
production code builds a `DelegatedTokenSource`, then a `GmailClient` or
`CalendarClient` around one shared `httpx.AsyncClient`.

## Access and the key

The key is the Secrets Manager value `GOOGLE_SERVICE_ACCOUNT_JSON`, stored in
the toolkit secret next to the other keys. One key serves every consumer, so
the name is not prefixed with a module.

The caller passes the scopes it needs (`domain/scopes.py`). A Workspace admin
authorizes the service account's Client ID for **every** scope any consumer
uses. Adding a consumer that needs a new scope means the admin updating the
grant first.

`google-auth` only signs the token request. Every call goes through `httpx`, and
every reply is parsed into a Pydantic model before it leaves `providers/`.

## Behaviour to know

- Gmail messages are fetched with `format=metadata` and a fixed header list, so a
  body is never requested.
- Transient failures (429, 5xx, and quota limits sent as 403) are retried with
  backoff, four attempts in all.
- A dropped Gmail history bookmark or Calendar sync token raises `CursorExpired`.
  The consumer decides how far back to re-read.
- A message deleted between listing and fetching is skipped.
- A live calendar event with no start or `iCalUID` is dropped, since it can't be
  keyed. A cancelled event may arrive with only its id and is kept.

## Not yet checked against Google's docs

These were built from memory, and each fails visibly if wrong:

- Gmail answers an expired `startHistoryId` with 404. 410 is treated the same.
- Calendar answers an expired sync token with 410.
- Whether Calendar issues a sync token when the first request has `timeMin` and
  `timeMax`. `CalendarPage.next_sync_token` is `None` when it doesn't.
- Whether the delegation accepts an alias address as the mailbox. Use primary
  addresses.
- That quota limits arrive as 403 with a `rateLimitExceeded` reason.
