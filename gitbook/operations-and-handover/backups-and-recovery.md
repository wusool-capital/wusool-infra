# Backups and recovery

No recovery-time objective, recovery-point objective, scheduled restore test,
or completed restore test is recorded for any system.

## What is protected

| Data | Protection | Gaps |
| --- | --- | --- |
| PostgreSQL (RDS) | Encrypted; deletion protection; 7 days of automated backups with point-in-time restore; a final snapshot kept on deletion | Single availability zone; no AWS Backup plan, cross-region copy, or manual snapshot schedule |
| n8n workflows, credentials, executions | None | **No backup at all.** Losing the instance volume loses everything. |
| Report and article content | Held in Sanity, including each report's rendered HTML | No export or backup in the repository; Sanity's Free plan keeps limited history |
| Webflow site and CMS items | Webflow's own features only | No export in the repository; report cards can be rebuilt by republishing in Sanity |
| Attio | Attio's own features only | No export in the repository |
| OpenTofu state | Versioned, encrypted S3 bucket that can't be destroyed by OpenTofu | None |
| Scribe update feed | Versioned S3 bucket; old versions kept 90 days | None |
| CloudTrail logs | Versioned S3 bucket | None |
| Local Scribe recordings | Only on each user's Mac | Not backed up centrally |

## Verify database protection

1. In AWS, open the RDS instance and confirm deletion protection, encryption,
   automated backups, and the retention window.
2. Confirm a recent restorable point exists, without copying data or
   credentials.
3. Check recent deploy and migration runs for failures.
4. Record the date, environment, oldest and newest restorable points, and
   operator in the client's operations register.

**If verification fails:** pause risky schema or infrastructure changes and
escalate to the database owner.

## Recover PostgreSQL

Recovery means restoring to a new instance, never undoing in place.

1. Declare the incident, stop writes or set a clear recovery point, and choose
   a snapshot or point in time with the data owner.
2. Keep the existing instance. Restore to a new, isolated RDS instance.
3. Check the schema revision, key business data, application connectivity,
   and Attio reconciliation against the restored database.
4. Prepare a reviewed OpenTofu change to adopt the restored instance, by
   importing it or updating state. Changing `snapshot_identifier` on the
   existing instance does nothing: the module ignores changes to it.
5. Cut over in an agreed window, then run health and critical user-flow
   checks and watch the logs and sync.
6. Keep the old instance until the data owner accepts the recovery.

If PostgreSQL is lost entirely, the nightly resync can rebuild the CRM mirror
from Attio. Tool runs, match history, and meetings exist only in PostgreSQL,
so they need the RDS backups.

See `docs/runbooks/database-and-migration-failure.md` for the step-by-step
procedure.

## Recover other systems

- **Reports:** republishing a report in Sanity re-renders it and rebuilds its
  Webflow card.
- **n8n:** with no backup, only the infrastructure can be rebuilt; workflows
  and credentials must be re-created by hand. Adding a snapshot schedule is an
  open handover item.

Escalate any unclear recovery point, incompatible migration, missing secret,
proposed instance deletion, or reconciliation mismatch.
