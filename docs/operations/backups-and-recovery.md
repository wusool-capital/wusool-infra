# Backups and recovery

The repository configures each PostgreSQL RDS instance with encrypted storage,
deletion protection, seven days of automated backup retention, and a final
snapshot on managed deletion. The module can create an RDS instance from a
specified snapshot.

No repository evidence confirms backup coverage for the self-hosted n8n data
volume, Attio, Slack, Cloudflare, or local WusoolScribe data. These services may
have vendor or manual recovery features, but they are **unverified for this
handover**. No recovery-time objective, recovery-point objective, scheduled
restore test, or last successful restore test is recorded.

## Verify database protection

1. In AWS, select the intended RDS instance and confirm deletion protection,
   encryption, automated backups, and the current retention window.
2. Confirm a recent restorable point exists and note its time without copying
   database contents or credentials.
3. Check recent database-related deployment and migration runs for failures.
4. Record the verification date, environment, oldest/newest restorable point,
   and operator in the client operations register.

**Expected outcome:** both environments show recent restorable points within
the configured seven-day window.

**If verification fails:** halt risky schema or infrastructure changes and
escalate to the database/infrastructure owner. Create a manual snapshot before
work only after confirming storage, encryption, retention, and access policy.

## Recover PostgreSQL from a snapshot

Recovery is a planned infrastructure operation, not an in-place undo.

1. Declare the incident, stop writes or otherwise establish a known recovery
   boundary, and select a snapshot or point in time with the data owner.
2. Preserve the existing instance. Restore to a new isolated RDS instance first.
3. Validate schema revision, row-level business checks, application connectivity,
   and the required Attio reconciliation against the restored database.
4. Prepare and review the OpenTofu change needed to adopt or route traffic to the
   restored instance. Never change `snapshot_identifier` on an existing managed
   instance expecting an in-place restore; replacement can destroy data.
5. Cut over in an agreed maintenance window, run application health and critical
   user-flow checks, and monitor logs and sync behavior.
6. Retain the previous instance until the data owner accepts the recovery, then
   follow the reviewed decommission plan.

**Expected outcome:** the application uses the validated restored database and
Attio/PostgreSQL reconciliation is complete.

**Escalate** any unclear recovery point, incompatible migration, missing managed
secret, proposed instance destruction, or reconciliation mismatch. A qualified
owner must define and test n8n backup/recovery before this platform can claim
complete disaster-recovery coverage.
