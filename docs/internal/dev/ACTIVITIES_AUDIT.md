# Activities audit: one history for every system action

> Internal execution detail retained outside the client-facing GitBook
> navigation. Findings for Linear AZM-150.

## Verdict

`activities` can be the single timeline of business events. It cannot do that
job today, and it should not store the detail itself.

**Recommendation:** keep the per-domain ledgers (`tool_runs`, `match_results`,
`meetings`, `command_runs`, `deal_stage_events`, `signals`) as the source of
truth. Make `activities` a thin, append-only index with one row per business
event: who (actor), did what (`event_type`), to which record (subject), when
(`ts`), with what result (`outcome`), and a typed FK to the ledger row that
holds the detail. It never copies ledger data.

This is not a raw audit log. Raw Attio deliveries go to `attio_raw_events`.

## What changed

This change implements the recommendation in one PR, with no data-engineer
sign-off yet (see [Review](#review)).

- **Schema** (three Alembic migrations): `activities` gains `event_type`,
  `actor_type`, `actor_ref`, `idempotency_key` and six typed ledger FKs;
  `command_runs` is new; `signals` gets a dedup key and run/meeting links;
  `attio_raw_events` gets a `received_at` index.
- **Code**: a new `app/modules/activities` module owns the vocabulary, the typed
  payloads, one recorder (`SqlAlchemyActivityRecorder`) and the deal-stage
  recorder. Writers in `ddl_commands`, `matching_engine`, `meetings` and
  `lead_magnets` call it on their own session. `attio_raw_events`,
  `attio_sync_state` and `deal_stage_events` are now written.
- **Bug fix**: the role-sync bug is fixed and covered by tests.

## How it is used today

This section describes the code **before** this change. Read from code; numbers
are not verified, see [Volume and quality](#volume-and-quality).

| Item | Finding |
| --- | --- |
| Writers | Two live writers. The Attio webhook (`ddl_commands/persistence/attio_sync.py`, `_log_activity`) and lead magnets (`lead_magnets/persistence/tool_runs_repository.py`, `_log_activity`). A one-off `backfill-activities.ps1` loaded history. |
| Readers | None. No API, Slack view, matching or discrepancy code reads the table. |
| Webhook rows | `source='attio_webhook'`. They record that a sync happened, not the business action. No actor, no channel, no diff, `payload` is `{}`. |
| Lead magnet rows | One per submission. `payload` is a raw copy of the submission, including questionnaire answers. |
| Actor | `actor_attio_id` is never set. No system actor exists. |
| Idempotency | None. Every webhook delivery appends a row. |
| Deletes, nightly resync | Never logged. The resync is excluded on purpose, to avoid flooding the table. |

## Coverage

| Action | Where | Activity before | Ledger | New event type |
| --- | --- | --- | --- | --- |
| CRM record created, updated, deleted (Attio webhook) | `ddl_commands/persistence/attio_sync.py` | Yes, generic, create/update only | `attio_raw_events` | `crm.record_created`, `crm.record_updated`, `crm.record_deleted` |
| Deal stage change | `sync_deal`, `matching_engine/application/approvals.py` | No | `deal_stage_events` | `deal.stage_changed` |
| Slack `/add-seller`, `/add-buyer` | `ddl_commands/api/slack/handlers/actions.py`, `api/seller_write.py` | Echo only, no actor | `command_runs` | `seller.added`, `buyer.added` |
| Slack `/edit-seller`, `/edit-buyer` | same | Echo only, no actor | `command_runs` | `seller.edited`, `buyer.edited` |
| Discovery auto-create seller | `discovery/providers/discovery/seller_writer_adapter.py` | Echo only | `command_runs` | `seller.added` |
| Match run | `matching_engine/application/matching/use_cases.py` | No | `match_results` | `match.run_completed` |
| Match approve, reject | `matching_engine/application/approvals.py` | No | `match_results` | `match.approved`, `match.rejected` |
| Meeting published to Attio | `meetings/application/publish.py` | Echo of the note only | `meetings` | `meeting.published` |
| Meeting deleted | `meetings/application/delete.py` | No | `meetings` | `meeting.deleted` |
| Lead magnet submission | `lead_magnets/persistence/tool_runs_repository.py` | Yes, with payload copy | `tool_runs` | `lead_magnet.submitted` |
| Nightly full resync | `ddl_commands/scripts/attio_sync_full_resync.py` | No, by design | `attio_sync_state` | none (state, not history) |
| `/enrich-*`, `/check-buyer` | `enrichment`, `discrepancies` | No | none | none. They never write; the edit form they open does. |

Ranked by value for a timeline: Slack add and edit with actor, match decisions,
deal stage changes, meetings, deletes, then match runs.

## Purpose decision

The target schema describes `activities` as a CRM touch log. The code already
mixes touch-log and system rows. Two options:

| | Extend `activities` | Separate audit log |
| --- | --- | --- |
| Readers | One timeline query | Two sources to merge |
| Existing data | Backfilled in place | Two tables to keep consistent |
| Risk | Table must stay thin | Duplicates ledger detail |

Decision: extend. No code reads `activities`, only two writers exist, and the
`tool_run.py` docstring already frames it as the human timeline over a machine
ledger.

## Design rules

- **Link, don't copy.** Typed nullable FKs to the ledger row. A CHECK allows at
  most one link per row. `payload` carries only the event's own facts, such as
  changed field names.
- **`ts` is event time.** `created_at` is insert time. They differ only for
  backfilled rows and for deal stage changes, where Attio's `stage_changed_at`
  is used.
- **Actor.** `actor_type` is always set: `attio_member`, `attio_api_token`,
  `attio_system`, `slack_user`, `scribe_install`, `website_visitor`, `system`,
  `unknown`. `actor_ref` holds the raw id. `actor_attio_id` is set only for an
  Attio member that exists in `users`. There is no Slack-to-`users` mapping.
- **Idempotency.** Writers with a stable id set `idempotency_key`
  (`lead_magnet.submitted:{run_id}:{status}`, `match.approved:{match_result_id}`).
  Webhook rows have no stable event id, so they have none.
- **Failure isolation.** The recorder writes inside a savepoint and swallows
  errors. An activity failure never aborts the business write.
- **Vocabulary.** `event_type` is `domain.verb`, enforced by a CHECK on format.
  The closed list lives in a Python `StrEnum`. `actor_type` and `subject_type`
  have closed CHECKs.

## Overlap with other tables

| Table | Role after this change |
| --- | --- |
| `tool_runs` | Lead-magnet ledger. `activities.tool_run_id` links to it. |
| `match_results` | Matching ledger. Linked by `match_result_id`. |
| `meetings`, `notes` | `meetings` is the Scribe ledger, linked by `meeting_id`. `notes` is an Attio mirror and stays separate. |
| `command_runs` (new) | Ledger for Slack and discovery add and edit commands, including failed and partial writes. Linked by `command_run_id`. |
| `deal_stage_events` | Now written by the webhook and by a match approval, each comparing the stored stage under a row lock so the webhook echo of an approval adds nothing. Linked by `deal_stage_event_id`. |
| `signals` | Schema prepared only (dedup key, run and meeting links, closed `source` list); nothing writes it yet. Linked by `signal_id`. |
| `attio_raw_events` | Now written once per webhook event, pruned after 90 days by the nightly resync. No idempotency key: events carry only ids, so two real updates look identical. Not part of the timeline. |
| `attio_sync_state` | Now written by the nightly resync (`attio_full_resync`). `last_synced_at` moves only on a clean run. State, not history. |

AZM-148 plans to write LinkedIn activity into `activities`. Those rows are
cited outside events about a buyer, so they belong in `signals`. AZM-148 is
out of scope here, but its design should follow this decision.

## Volume and quality

Not verified. Only a disposable local database was available, so none of
these ran against real data. Run them on the approved read-only prod copy
before the data-engineer review.

```sql
-- Rows by source and subject type
SELECT source, subject_type, count(*) FROM activities GROUP BY 1, 2 ORDER BY 3 DESC;

-- Rows per day
SELECT date_trunc('day', created_at) AS day, count(*) FROM activities GROUP BY 1 ORDER BY 1 DESC LIMIT 60;

-- Webhook rows with an empty payload
SELECT count(*) FROM activities WHERE source = 'attio_webhook' AND payload = '{}'::jsonb;

-- Repeated webhook deliveries for one subject within 60 seconds
SELECT subject_type, coalesce(subject_attio_id, subject_uuid::text) AS subject, count(*)
FROM activities a
WHERE source = 'attio_webhook'
  AND EXISTS (
    SELECT 1 FROM activities b
    WHERE b.id <> a.id AND b.subject_type = a.subject_type
      AND b.subject_attio_id IS NOT DISTINCT FROM a.subject_attio_id
      AND b.subject_uuid IS NOT DISTINCT FROM a.subject_uuid
      AND abs(extract(epoch FROM (b.created_at - a.created_at))) < 60)
GROUP BY 1, 2 ORDER BY 3 DESC LIMIT 50;

-- Lead magnet payload size
SELECT percentile_cont(0.5) WITHIN GROUP (ORDER BY pg_column_size(payload)) AS p50,
       percentile_cont(0.95) WITHIN GROUP (ORDER BY pg_column_size(payload)) AS p95
FROM activities WHERE source = 'lead_magnet';

-- Orphans per subject type
SELECT 'Organization' AS subject_type, count(*) FROM activities a
  WHERE subject_type = 'Organization' AND NOT EXISTS (SELECT 1 FROM organizations o WHERE o.attio_id = a.subject_attio_id)
UNION ALL SELECT 'Person', count(*) FROM activities a
  WHERE subject_type = 'Person' AND NOT EXISTS (SELECT 1 FROM person p WHERE p.attio_id = a.subject_attio_id)
UNION ALL SELECT 'SellerRole', count(*) FROM activities a
  WHERE subject_type = 'SellerRole' AND NOT EXISTS (SELECT 1 FROM seller_roles r WHERE r.id = a.subject_uuid)
UNION ALL SELECT 'BuyerRole', count(*) FROM activities a
  WHERE subject_type = 'BuyerRole' AND NOT EXISTS (SELECT 1 FROM buyer_roles r WHERE r.id = a.subject_uuid)
UNION ALL SELECT 'Deal', count(*) FROM activities a
  WHERE subject_type = 'Deal' AND NOT EXISTS (SELECT 1 FROM deals d WHERE d.attio_id = a.subject_attio_id)
UNION ALL SELECT 'Note', count(*) FROM activities a
  WHERE subject_type = 'Note' AND NOT EXISTS (SELECT 1 FROM notes n WHERE n.attio_id = a.subject_attio_id);

-- Rows with no actor
SELECT source, count(*) FROM activities WHERE actor_attio_id IS NULL GROUP BY 1;
```

Usefulness test, to run on three real buyers: "what happened to this buyer in
the last 30 days" with
`SELECT * FROM activities WHERE subject_type IN ('Organization','BuyerRole') AND subject_attio_id = :id ORDER BY ts DESC`.
From the code alone the answer today is no. The rows say "synced" with no
actor, no change and no result.

## Risks

| Risk | Status |
| --- | --- |
| Role-sync bug | **Reproduced and fixed.** `sync_buyer_role` and `sync_seller_role` logged `subject_uuid=None` when the webhook entry was missing from the sibling list query. That violated `activities_subject_present` and rolled back the whole role upsert, after Attio `is_active` PATCHes had landed. The webhook handler swallowed the error. The regression tests fail with that exact CHECK violation against the original schema and pass with the fix, which adds the fetched entry to the sibling list. |
| Raw submission data in `payload` | Lead-magnet rows copy answers and PII. Fixed for new rows: they link `tool_run_id` instead. Existing rows are left as they are. |
| Unbounded webhook append | Every delivery adds a row. Not changed. The volume query decides whether retention is needed. |
| Hard-deleted roles | `sync-source-to-prod.ps1` hard-deletes role rows, which orphans activities. Documented, not changed. |
| Attio webhook actor | The event shape is unverified against a real delivery. If absent, rows get `actor_type='unknown'`. |
| Deal stage changes in the nightly batch | The batch path does not write `deal_stage_events`. Gap documented. |
| Prod volume | The migration backfills in one transaction and builds plain indexes. Confirm the table is small first. |
| Recorder swallows errors | By design, so a history failure cannot abort a business write. A bug there is silent apart from an `activity_record_failed` log line: one such bug (an ISO string where asyncpg wants a `datetime`) was found by a test during this change. Alert on that log line. |
| Webhook echoes | A Slack seller add also produces a `crm.record_created` row from the webhook echo, with `actor_type` `attio_api_token`. Readers wanting only human actions filter on `actor_type`. |
| Raw event growth | `attio_raw_events` gets a row per webhook event until the nightly prune. Volume is unmeasured. |
| `signals` schema | A static-analysis draft, never checked against the live database. |

## Review

The recommendation and the three migrations need data-engineer sign-off before
merge. Not done here: counting queries on real data, and a check of the live
`signals` table against its draft model.

## Follow-ups

- Write `signals` from buyer meeting transcripts, and move AZM-148's LinkedIn
  activity to `signals`.
- Fix `sync-source-to-prod.ps1` hard-deleting role rows, which orphans activities.
- Add a write path for deal stage changes found only by the nightly batch resync.
- Decide retention for `activities` once the volume queries have run.
- A timeline read path (API or Slack view); nothing reads `activities` yet.
