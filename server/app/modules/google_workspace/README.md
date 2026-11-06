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

## Checked against Google's docs (6 Nov 2026)

- **Expired Gmail bookmark is a 404.** History is kept "at least one week and often
  longer", and the client must then do a full sync
  ([sync guide](https://developers.google.com/workspace/gmail/api/guides/sync)).
- **Expired Calendar sync token is a 410** (`fullSyncRequired`); the client must
  clear its store and re-sync
  ([errors](https://developers.google.com/workspace/calendar/api/guides/errors)).
- **A sync token rules out `timeMin`, `timeMax` and `updatedMin`, and `showDeleted`
  may not be false.** Every other parameter must match the first request
  ([events.list](https://developers.google.com/workspace/calendar/api/v3/reference/events/list)).
  The backfill and the incremental calls share their parameters for this reason.
- **A bounded first sync is allowed.** Google's own sample sets `timeMin` on the
  full sync ([sync guide](https://developers.google.com/workspace/calendar/api/guides/sync)).
- **Rate limits come as 403 or 429.** Calendar's `rateLimitExceeded` "can return
  either 403 or 429" and `userRateLimitExceeded` is a 403; both get exponential
  backoff ([errors](https://developers.google.com/workspace/calendar/api/guides/errors)).
- **`gmail.metadata` cannot use the `q` filter**, so the date-filtered backfill
  needs `gmail.readonly`. `history.list` accepts either scope
  ([messages.list](https://developers.google.com/workspace/gmail/api/reference/rest/v1/users.messages/list)).
- **The delegation token request matches Google's example:** claims `iss`, `sub`,
  `scope`, `aud`, `iat` and `exp` (at most one hour), signed RS256, with the
  `jwt-bearer` grant type
  ([service accounts](https://developers.google.com/identity/protocols/oauth2/service-account)).
- **Gmail quota is 6,000 units a minute per user.** `messages.get` costs 20,
  `messages.list` 5, `history.list` 2 and `getProfile` 1
  ([usage limits](https://developers.google.com/workspace/gmail/api/reference/quota)),
  so a mailbox allows about 300 message fetches a minute. The client paces its
  fetches to 250 a minute per mailbox. A 12-month backfill of a large mailbox is
  therefore slow by design: 20,000 messages take about 80 minutes.

## Still not documented

- Whether `sub` may be an alias address. Google describes it as "the email address
  of the user". Use primary addresses.
- Whether a first request with `timeMax` as well as `timeMin` still returns a sync
  token. `CalendarPage.next_sync_token` is `None` when it doesn't. The documented
  fallback is `updatedMin`, which answers 410 `updatedMinTooLongAgo` when too old.

## Worth knowing when you consume it

An incremental Calendar sync cannot be limited by time, so it returns changes to
events of any date. The consumer must drop what falls outside the window it keeps.
