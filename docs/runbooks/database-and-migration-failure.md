# Incident: PostgreSQL unavailable or migration failure

## Purpose

Diagnose private PostgreSQL/RDS failures and failed Alembic migrations used by
Toolkit deployments.

## Impact

Toolkit readiness, Slack operations, matching, enrichment, meetings, lead-tool
bookkeeping, and Attio mirror processing may fail. A migration failure blocks
the new Toolkit image from rolling out.

## Symptoms

- Toolkit `/health` is 200 but `/readiness` or `/ready` returns HTTP 503.
- `/toolkit-status` reports the database as unreachable.
- GitHub Actions fails at `alembic upgrade head` before Toolkit rollout.
- The database schema workflow fails because the Alembic graph has more than
  one head, or a migration branch cannot be applied cleanly.
- RDS connectivity, backup, or instance alarms indicate a database problem.

## Severity

P1 — Treat confirmed data loss or corruption as P0.

## Immediate Actions

1. Stop repeated deployments and record environment, deployment run, migration
   revision, UTC time, and affected workflow.
2. Check whether the issue is connectivity, credentials, schema compatibility,
   or data integrity.
3. Preserve migration stdout/stderr and the GitHub Actions run URL without
   copying database credentials or customer data.

## Diagnosis

1. Confirm the intended `dev` or `prod` environment and AWS identity with
   `aws sts get-caller-identity`.
2. Verify the private RDS instance, deletion protection, encryption, backup
   retention, and recent restorable point in AWS. The configured retention is
   seven days, but live backup state is NOT VERIFIED.
3. For read-only connectivity and schema checks, use the verified tunnel and
   credential procedure in `server/scripts/postgres-sync/rds-tunnel-runbook.md`.
4. Inspect the failed deployment's SSM invocation output. The deployment runs
   the exact image's `python -m alembic upgrade head` through SSM before rolling
   the application.
5. For a migration-graph failure, from `server/` run the repository-verified
   read-only checks `uv run alembic heads` and `uv run alembic history`. The
   CI schema check also requires exactly one head and runs `uv run alembic
   check` against a disposable PostgreSQL database.
6. Inspect `server/alembic/versions/` and the migration files' revision and
   `down_revision` relationships for an unresolved branch or source merge
   conflict. A migration that partially applied requires database-owner review
   before any retry.

## Recovery

1. For a transient connection or SSM failure, restore access through the
   approved AWS/SSM path and retry only the reviewed deployment workflow.
2. For multiple heads or a migration conflict, stop the deployment and create a
   new PR. Add an Alembic merge migration whose parent revisions are the
   unresolved heads; preserve both intended migration paths and do not rewrite
   an already-applied migration. Have the application/database owner review the
   migration, then let the database schema workflow validate the graph against
   disposable PostgreSQL before merging the PR.
3. Merge that PR into `dev` so the verified `Deploy dev` workflow runs again.
   Confirm the migration completes, Toolkit health/readiness checks pass, and
   the affected flow works in development. Only then promote the same fix to
   `prod`, where the matching deployment workflow will run again.
4. For any migration failure, do not downgrade automatically. Choose a
   forward fix or a compatibility-preserving application rollback with the
   database owner. If production has already partially applied a migration,
   do not retry until the live revision and affected objects are verified.
5. For suspected data loss, preserve the existing RDS instance and follow the
   planned snapshot/point-in-time recovery procedure in
   `gitbook/operations-and-handover/backups-and-recovery.md`. Restoring to a new isolated RDS
   instance and validating Attio reconciliation requires explicit human
   approval.

## Validation

- `/readiness` returns HTTP 200 with `{"status":"ready"}`.
- The failed migration is either completed and verified or has an approved
  forward recovery plan.
- The affected Toolkit flow and relevant Attio/PostgreSQL reconciliation pass.
- No unexpected RDS replacement or deletion appears in the reviewed plan.

## Rollback

No verified generic database rollback mechanism was found. Do not use
`alembic downgrade` as routine recovery. Application rollback is safe only
after schema compatibility is explicitly confirmed.

## Escalation

Escalate immediately for partial migrations, unavailable backups, unclear
recovery point, credential mismatch, destructive OpenTofu plan, or any data
integrity concern. Database and infrastructure owners are NOT VERIFIED here.

## Do Not

- Do not reset, truncate, or delete the production database.
- Do not change `snapshot_identifier` on an existing managed instance.
- Do not edit migration files in production or hand-edit `alembic_version`.
- Do not edit mirrored CRM fields directly while sync recovery is in progress.
- Do not expose the private RDS instance or place credentials in logs.

## Root Cause Follow-Up

Record the migration revision/head state, SSM invocation, RDS state, recovery
point, and compatibility decision. Schedule an isolated restore test if one
has not been recorded.
