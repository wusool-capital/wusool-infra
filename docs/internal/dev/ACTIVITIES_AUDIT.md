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

## How it is used today

Read from code. Numbers are not verified, see [Volume and quality](#volume-and-quality).

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
| `command_runs` (new) | Ledger for Slack and discovery add and edit commands, including failed and partial writes. |
| `deal_stage_events` | Now written. Linked by `deal_stage_event_id`. |
| `signals` | Schema prepared only. Buyer signals with `source` in transcript, news, linkedin, jobs. |
| `attio_raw_events` | Now written, pruned after 90 days. Not part of the timeline. |
| `attio_sync_state` | Now written by the nightly resync. State, not history. |

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
| Role-sync bug | Confirmed in code. `sync_buyer_role` and `sync_seller_role` log `subject_uuid=None` when the webhook entry is missing from the sibling list query. That violates `activities_subject_present` and rolls back the whole role upsert, after Attio `is_active` PATCHes have landed. The error is swallowed by the webhook handler. Fixed in this change with a regression test. |
| Raw submission data in `payload` | Lead-magnet rows copy answers and PII. Fixed for new rows: they link `tool_run_id` instead. Existing rows are left as they are. |
| Unbounded webhook append | Every delivery adds a row. Not changed. The volume query decides whether retention is needed. |
| Hard-deleted roles | `sync-source-to-prod.ps1` hard-deletes role rows, which orphans activities. Documented, not changed. |
| Attio webhook actor | The event shape is unverified against a real delivery. If absent, rows get `actor_type='unknown'`. |
| Deal stage changes in the nightly batch | The batch path does not write `deal_stage_events`. Gap documented. |
| Prod volume | The migration backfills in one transaction and builds plain indexes. Confirm the table is small first. |
| `signals` schema | A static-analysis draft, never checked against the live database. |

## Review

The recommendation needs data-engineer sign-off before the migrations merge.
