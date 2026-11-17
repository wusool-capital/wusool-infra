# interactions

Reads Gmail and Google Calendar metadata for the team mailboxes and computes
the relationship fields Attio only calculates on its standard Companies and
People: last, first and next interaction, last interaction channel, owner and
subject, and connection strength. AZM-159 tracks the build.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Status

The module reads and stores Gmail and Calendar metadata and links it to CRM
records. `IngestService.run_pass()` does one pass, and `run_interactions_forever()`
runs it on a timer, off by default. After each pass a write round sends the
computed fields to Attio.

**Production runs it.** The loop is on, the write mode is `on`, and the scoring
settings come from the prod secret, not the defaults here: half-life 365 days,
meeting points 2, two-way bonus 1.0 and label cutoffs 5.7, 17, 37 and 48. The
shadow-week report (`scripts/calibrate_strength.py`) passed on those values. Contact creation
is on too, at most 20 Persons per round.

## Structure

```
domain/         # Touch, scoring, summarize, ignore filter, linking rules, month windows
application/
  ingest.py     # IngestService: backfill, polling, recovery, linking, retention
  mapping.py    # fetched Gmail and Calendar data -> rows to store (pure)
  calibration.py  # run_calibration(): our labels against Attio's, in memory
  attio_write.py  # AttioWriteService: one round of changed-value writes to Attio
  attio_seed.py   # AttioSeedService: records what Attio holds before the first write
  auto_create.py  # AutoCreateService: new Persons and Organizations for outside contacts
  review_digest.py  # ReviewDigestService: the daily Slack post of cases to review
  ports/        # InteractionStorePort, RecordDirectoryPort, TouchReaderPort, StrengthSourcePort
persistence/    # SqlAlchemyInteractionStore, SqlAlchemyRecordDirectory, SqlAlchemyTouchReader,
                # SqlAlchemyCandidateSource, SqlAlchemyReviewStore, lock
providers/      # AttioStrengthSource, AttioSeedSource (reads), AttioRecordWriter (paced PATCH),
                # AttioRecordCreator, SlackDigestPoster
scripts/        # calibrate_strength.py (shadow-week report), seed_attio_sent_values.py
bootstrap.py    # run_interactions_forever(): wires everything and runs the poll loop
config.py       # InteractionsSettings: every tunable, prefixed interactions_
```

## Shadow-week calibration

`python -m app.modules.interactions.scripts.calibrate_strength` compares our label for each
Organization with Attio's `strongest_connection_strength` on the matching Company. It reads
only and writes nothing to Attio or Postgres. Run it in the deployed container, never from a
laptop against the dev or prod database. Add `--mismatches PATH` to save record ids. Add
`--scores PATH` to save a CSV of record id, Attio's label and our raw score, so label cutoffs
can be tuned offline. It holds no names or subjects.

A Company is matched to an Organization by domain, the same way linking does. It is compared
only when Attio's label is a fair reference. Everything else is counted in a named bucket:
no Attio label, a label we don't recognise, no identifiable strongest user, strongest user
is `tech@`, strongest user is a mailbox we don't read, no
Organization for the domain, and a domain or Organization shared by several records. Each
percentage prints its denominator.

A Company with an Attio label but no interactions on our side is compared as Very weak, and
the report counts them. On prod, Attio labelled 87% of those Very weak.

The go-live gate is 80% exact match and 95% within one level. Attio scores every team
mailbox and we read only `INTERACTIONS_MAILBOXES`, hence the mailbox bucket. Cancelled
meetings never count.

## Writing to Attio

`AttioWriteService.run_round()` runs after each pass, in the same advisory lock. For
each Organization and Person it computes the 13 fields, compares them with
`attio_sent_values`, and PATCHes only what changed, then records what was sent. Attio is
written first.

- **Seed first.** `scripts/seed_attio_sent_values.py` stores what Attio holds today
  (`value`) and the live Company or Person value (`baseline`, joined by `legacy_attio_id`).
  Nothing is written for an object until it has run.
- **Dates only move the right way.** A first date takes the earliest of computed, stored
  and baseline; a last date the latest. Channel, subject and owner follow the last date.
- **Hugo's records.** If the baseline strongest user is an unread mailbox, strength and
  strongest user are left alone.
- **The score.** The numeric score behind strength goes to `connection_strength_score` on
  `organizations` and `person`, straight to Postgres, only when it changed. It has no Attio
  attribute, so the webhook never overwrites it. It is skipped where strength is left alone.
- **Clearing.** A field that should be empty is sent as an empty list, which live Attio
  accepts for every field kind. A label with no recent interactions drops to Very weak
  instead of being emptied, and the strongest user is kept. First and last dates are never
  cleared.
- **Safety.** `off` by default; `dry_run` logs counts only; refuses to run while
  `ATTIO_IS_TEST` is set; capped per round; one failing record never stops the round.
- **Alarm.** A clean real round logs `interactions_attio_sync_ok`. The prod alarm
  (`interactions_sync_alarm`) fires after 30 minutes without it.

## Creating contacts

`AutoCreateService.run_round()` runs after the write round. It reads unlinked outside addresses
with a two-way thread or an uncancelled meeting (`SqlAlchemyCandidateSource`), filters them with
`domain/creatable.py`, and creates a Person and, unless the domain has one, an Organization in
Attio, both tagged Lead Source Detail "Email sync".

- **Duplicates.** Postgres lags the webhook, so each create is recorded in `auto_create_keys`
  right after Attio accepts it, and `person_exists` asks Attio by email as a second check.
- **Failures.** An address Attio rejects three times is dropped until the next restart, so it
  can't use up every round's cap.
- **Names.** The Person's name is the sender's display name (`interaction_participants.display_name`,
  filled for mail read since this column was added), else the address, as the sync bot does.
- **Shared cases.** An address or domain that matches several records creates nothing. Ingest saves
  it to `interaction_review_items`; one that is fixed resolves itself, and a dismissed one stays
  dismissed. `ReviewDigestService` posts the cases it has not listed yet, once a day with the
  purge, to `INTERACTIONS_REVIEW_SLACK_CHANNEL`.
- **Safety.** `INTERACTIONS_AUTO_CREATE_MODE` is `off` by default; `dry_run` logs counts only;
  capped per round; refuses to run while `ATTIO_IS_TEST` is set. Free-email domains extend the
  benchmark's `FREE_MAIL` list.

## Deal rollup

A Deal has a seller Organization and a buyer, a Person or an Organization. `domain/deals.py`
merges the touches of both sides, counting a touch once however many sides hold it, and the
same `summarize` and `plan_record` run on the result. Only five of the 13 fields exist on a Deal,
so `fields_of(AttioObject.DEAL)` limits what is written.

- **Reading Deals.** Through `ddl_commands.list_live_deal_parties`, the module that owns `deals`.
- **No score.** A Deal's strength has no score column; the score store refuses the object.
- **Unread mailbox.** If the buyer's or seller's baseline strongest user is a mailbox we don't read,
  the Deal's strength is left alone.
- **Safety.** `INTERACTIONS_DEAL_ROLLUP_MODE` is `off` by default and runs inside the write step.
  Seed first: an unseeded object is reported and writes nothing. It is only counted as unseeded
  when the mode is not off, so it can't silence the stale-sync alarm.

## Reading CRM records

`persistence/directory.py` gets Organizations from `OrganizationRepository.list_live_domains()`
and Persons from `ddl_commands.list_live_person_emails()`. Both are read-only lookups in the
modules that own those tables. This module writes only its own three tables.

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
- **Calendar's far edge:** Google's changes list never mentions a meeting nobody edited, so
  a meeting that has just come inside the 180-day window would be missed. Each poll
  therefore also reads that new slice, from where the window ended at the last sync
  (minus a day) to where it ends now. It is usually one empty request. The sync
  position moves only after this read works, so a failure leaves no gap.
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
