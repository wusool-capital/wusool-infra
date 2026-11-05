# interactions

Reads Gmail and Google Calendar metadata for the team mailboxes and computes
the relationship fields Attio only calculates on its standard Companies and
People: last, first and next interaction, last interaction channel, owner and
subject, and connection strength. AZM-159 tracks the build.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Status

Read-only and unfinished. The module holds the pure domain rules, the settings
and the Gmail and Calendar clients. Storing the fetched rows, the ingest pass
and the poll loop come next. Nothing writes to Attio: that is a later PR,
gated by the shadow-week calibration. Nothing calls the Google clients yet.

## Structure

```
domain/                  # Touch, scoring, summarize, ignore filter, addresses, fetched-data types
application/ports/       # MailSourcePort, CalendarSourcePort, TokenSource (Protocols)
application/errors.py    # CursorExpired
providers/google/        # auth (delegated tokens), gmail, calendar, models, http (retries)
config.py                # InteractionsSettings: every tunable, prefixed interactions_
```

Planned: `persistence/` (the three tables from migration `d5f8b2a17c94`),
`application/ingest.py` and `retention.py`, `bootstrap.py` (the poll loop).

## Google access

A service account with domain-wide delegation acts as each mailbox. The key
is the Secrets Manager value `INTERACTIONS_GOOGLE_SERVICE_ACCOUNT_JSON`, held
in the existing toolkit secret next to the other keys. `google-auth` only
signs the token request; all calls go through `httpx`, and every reply is
parsed into a Pydantic model in `providers/google/models.py`.

Gmail messages are fetched with `format=metadata` and a fixed header list, so
a body is never requested. Failed calls with a transient status are retried
with backoff; a dropped Gmail history bookmark or Calendar sync token raises
`CursorExpired` for the ingest pass to handle.

## Public contract

The names in `__init__.py`: `Touch`, `ScoringRules`, `InteractionSummary`,
`StrengthLabel`, `summarize`, `score_pair` and `label_for`.

## The scoring rule

Each pair of team member and outside contact gets a score. A record takes its
strongest pair.

- Points per touch: email sent 1, email received 1.5, meeting 4.
- A touch loses half its weight every 90 days.
- The score is multiplied by 1.5 when both sides emailed in the last 180 days.
- Labels: below 1 Very weak, 1 to 3 Weak, 3 to 7 Good, 7 to 15 Strong,
  15 and above Very strong. A lower bound is inclusive, an upper bound is not.

Every number lives in `InteractionsSettings` so the shadow week can tune it
without a code change.

## Rules worth knowing

- Addresses on `wusoolcapital.com` and `dopaminecap.com` are one team member.
- The same email sits in every mailbox it reached. Rows share a `dedupe_key`,
  and owner resolution picks one team member per key: the sender, then To over
  CC, then the stronger pair.
- Internal-only mail, spam, trash, drafts, chat, all-day and cancelled events,
  declined meetings, calendar notification mail and auto-replies never count.
- Only headers and calendar fields are fetched. Message bodies are never read
  or stored.
