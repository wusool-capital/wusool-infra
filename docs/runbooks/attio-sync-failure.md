# Incident: Attio to PostgreSQL synchronization failure

## Purpose

Recover production CRM mirror drift caused by a failed Attio webhook or nightly
full resynchronization.

## Impact

PostgreSQL-backed matching, Toolkit workflows, lead tools, and meeting
processing may use stale or incomplete CRM data. Attio remains the business
CRM of record.

## Symptoms

- An Attio change is visible in Attio but missing from PostgreSQL.
- `POST /webhooks/attio` deliveries are rejected or fail processing.
- The scheduled `nightly-attio-sync.yml` workflow fails or is skipped because no
  Toolkit instance is SSM-online.
- `validate-postgres.ps1` reports count, relationship, or environment-flag
  mismatches.
- CloudWatch/SNS reports a nightly resync failure.

## Severity

P1 — when production drift affects user-facing matching, lead tools, or critical
CRM workflows; otherwise P2.

## Immediate Actions

1. Record the Attio record ID, field, edit time, environment, workflow/run URL,
   and error without copying API keys or customer payloads.
2. Check whether the real-time webhook is still processing while the nightly
   job is impaired.
3. Do not manually patch mirrored PostgreSQL fields before understanding the
   sync failure; a later sync can overwrite the patch.

## Diagnosis

1. Confirm production scope: the source Attio workspace is shared, and
   `ATTIO_IS_TEST` separates environment records. A value explicitly marked
   test must not enter production.
2. Inspect the failed GitHub Actions nightly run and its SSM invocation output.
   The repository script is `.github/scripts/nightly-attio-resync.sh` and the
   remote command is `python -m app.modules.ddl_commands.scripts.attio_sync_full_resync`.
3. If the instance is unavailable, use the Toolkit outage runbook and confirm
   the current ASG-managed instance is SSM-online.
4. Check webhook signature/workspace rejection versus Attio API failure versus
   PostgreSQL connectivity. The endpoint is `POST /webhooks/attio`.
5. Run the verified read-only production validator through the RDS tunnel:
   `server/scripts/postgres-sync/prod/validate-postgres.ps1`.

## Recovery

1. Fix the identified access, instance, or dependency issue with the responsible
   owner; do not rotate credentials or alter webhook subscriptions without
   explicit human approval.
2. After understanding the failure, rerun the nightly workflow or its verified
   resync script. The script has bounded runtime/resources, prevents concurrent
   resyncs, streams output to the Toolkit CloudWatch log group, and cancels a
   timed-out SSM command.
3. For planned operator reconciliation, use
   `server/scripts/postgres-sync/prod/sync-all-to-prod.ps1` in dry-run mode
   first, then `-Apply` only after reviewing the output and receiving data-owner
   approval.
4. Run `validate-postgres.ps1` after synchronization and reconcile any remaining
   mismatch with the data owner.

## Validation

- The nightly workflow is successful and its SSM command completed successfully.
- The affected record is present and correct in PostgreSQL.
- `validate-postgres.ps1` passes for counts, relationships, and environment
  flags.
- A safe affected Toolkit flow reads the expected CRM data.

## Rollback

No verified sync rollback mechanism was found. Organizations/person records may
be soft-deleted, but deals, buyer roles, and seller roles can be hard-deleted by
reconciliation. Recovery from an incorrect destructive sync requires an
approved RDS point-in-time/snapshot recovery and Attio reconciliation.

## Escalation

Escalate for zero/abnormally low upstream data, a large test exclusion count,
hard deletes, webhook restoration failure, repeated SSM failures, or any
production data mismatch that cannot be explained. Data, Attio, and Toolkit
owners are NOT VERIFIED in this repository.

## Do Not

- Do not run production sync with `-Apply` before reviewing the dry run.
- Do not use source migration tooling as an emergency production reconciliation
  shortcut.
- Do not delete production rows, bypass signature/workspace checks, or expose
  Attio/RDS credentials.

## Root Cause Follow-Up

Preserve the workflow URL, SSM command status, record scope, validator output,
and whether webhook delivery continued. Verify alert delivery and document the
reconciliation result.
