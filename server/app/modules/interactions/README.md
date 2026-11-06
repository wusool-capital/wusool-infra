# interactions

Reads Gmail and Google Calendar metadata for the team mailboxes and computes
the relationship fields Attio only calculates on its standard Companies and
People: last, first and next interaction, last interaction channel, owner and
subject, and connection strength. AZM-159 tracks the build.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Status

Read-only and unfinished. The module reads and stores Gmail and Calendar
metadata and links it to CRM records. `IngestService.run_pass()` does one pass,
and `run_interactions_forever()` runs it on a timer, off by default. Nothing
writes to Attio: that is a later PR, gated by the shadow-week calibration.

## Structure

```
domain/         # Touch, scoring, summarize, ignore filter, linking rules, month windows
application/
  ingest.py     # IngestService: backfill, polling, recovery, linking, retention
  mapping.py    # fetched Gmail and Calendar data -> rows to store (pure)
  ports/        # InteractionStorePort, RecordDirectoryPort (Protocols) and the records they carry
persistence/    # SqlAlchemyInteractionStore, SqlAlchemyRecordDirectory, advisory lock
bootstrap.py    # run_interactions_forever(): wires everything and runs the poll loop
config.py       # InteractionsSettings: every tunable, prefixed interactions_
```

## The poll loop

`main.py`'s lifespan starts `run_interactions_forever()` beside the lead-magnet
sweeper and cancels it on shutdown. It returns at once, doing nothing, unless
**`INTERACTIONS_ENABLED=true`** and **`GOOGLE_SERVICE_ACCOUNT_JSON`** is a valid
key. A missing or malformed key is logged and never echoed.

Every `INTERACTIONS_POLL_INTERVAL_S` (900) it takes a Postgres advisory lock and
runs one pass. If another instance holds the lock, that round is skipped. This
matters because dev and prod can share a database and a Google tenant, and a
deploy briefly runs two containers. The lock lives on a connection of its own, so
a crashed process releases it. A failed pass is logged and the loop carries on.

Once a day, after a pass, it purges interactions older than
`INTERACTIONS_RETENTION_MONTHS` (12). A failed purge is retried on the next pass.

Turn it on in **one** environment only. It reads three real mailboxes.

## How a pass works

For each mailbox, Gmail and Calendar are synced separately. Each source keeps
one row in `mailbox_sync_cursors`.

- **First time:** Gmail's change bookmark is recorded *before* any mail is read, so
  mail that arrives during the backfill is picked up by the first poll. Then the
  last 12 months are read a page at a time. The page token is saved with each
  page, so a restart resumes. `backfill_completed_at` marks it done, and it never
  runs again for that mailbox.
- **After that:** only changes since the saved bookmark are read. The bookmark moves
  once every page of the poll is saved.
- **Expired bookmark or token:** Gmail re-reads from `last_synced_at` minus a day, so an
  outage of any length is covered. Calendar re-reads the full window.
- **No Calendar sync token** (if Google does not issue one): the next passes re-read the
  last seven days instead.

Rows are saved with their sync position in one transaction. A re-read email is
skipped, and a re-read meeting is updated in place, so a moved or renamed meeting
keeps one row. Meetings Google reports as cancelled are flagged.

Afterwards, outside addresses that have no Person or Organization are matched: a
unique address links its Person, and the domain (or a parent domain) links its
Organization. An address shared by several Persons, or a domain shared by several
Organizations, links nothing. Counts of those are reported; the review table that
will hold them comes in a later PR. Links are only ever filled in, never replaced.

`purge_expired()` deletes interactions older than the retention window.

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
