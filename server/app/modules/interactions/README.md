# interactions

Reads Gmail and Google Calendar metadata for the team mailboxes and computes
the relationship fields Attio only calculates on its standard Companies and
People: last, first and next interaction, last interaction channel, owner and
subject, and connection strength. AZM-159 tracks the build.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Status

Read-only and unfinished. The module holds the pure domain rules and the
settings. Storing the fetched rows, the ingest pass and the poll loop come
next. Nothing writes to Attio: that is a later PR, gated by the shadow-week
calibration.

## Structure

```
domain/       # Touch, scoring, summarize, ignore filter, internal-address rules
config.py     # InteractionsSettings: every tunable, prefixed interactions_
```

Planned: `application/` (ingest, retention), `persistence/` (the three tables
from migration `d5f8b2a17c94`), `bootstrap.py` (the poll loop).

## Google access

Reading Gmail and Calendar is the job of the
[`google_workspace`](../google_workspace/README.md) module, which this module
uses through its public names only. It owns the service-account key
(`GOOGLE_SERVICE_ACCOUNT_JSON`), delegated tokens and the typed clients, and
Scribe will reuse it. This module passes the scopes it needs: `GMAIL_READONLY`
and `CALENDAR_READONLY`.

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
