# Monitoring and incident response

CloudWatch retains n8n and Toolkit logs for 30 days. Infrastructure alarms feed
the environment alert topics; repository configuration routes operational
alerts to email and the shared infrastructure alert channel. Confirm live
subscriptions during handover because source code cannot prove that recipients
accepted them or that chat authorization remains active.

| Signal | Meaning | Automated action |
| --- | --- | --- |
| Toolkit has no in-service instance | The single-instance Auto Scaling Group is unavailable | A replacement instance is launched |
| Toolkit container health fails | Process is unhealthy while the host remains available | The container is restarted |
| Toolkit external `/health` fails | Public network path is unavailable | Alert only |
| Toolkit CPU exceeds its threshold | Sustained host pressure | Alert only |
| n8n EC2 status check fails | AWS detects host or instance impairment | Alert only |
| n8n CPU exceeds its threshold | Sustained host pressure | Alert only |
| GuardDuty or Security Hub finding | Potential security issue | Security notification |

The nightly Attio-to-PostgreSQL resync runs in GitHub Actions at 02:00
Asia/Dubai. It currently has **no automatic failure notification**; operators
must inspect its run history. The real-time Attio webhook complements this job
but does not remove the need to check missed or failed nightly runs.

## Incident procedure

1. Record the environment, start time in UTC, affected users and workflows,
   recent deployment, and the exact error. Avoid customer data in the record.
2. Confirm scope using the service health endpoint and one safe user-flow check.
3. Check GitHub deployment and nightly-sync history for a correlated failure.
4. Inspect CloudWatch alarms and logs for the same time window. For Toolkit,
   distinguish host replacement, container restart, and external reachability;
   they have different responses.
5. Restore service with the smallest reversible action: allow self-healing to
   complete, restart the affected container through Systems Manager, or roll
   back the responsible release.
6. Verify health and the affected user flow, monitor for recurrence, and record
   the resolution and follow-up owner.

**Expected outcome:** health returns, the user flow succeeds, and the incident
record contains enough evidence for follow-up without secrets or private data.

## Escalation guidance

- Escalate immediately for suspected credential exposure, unauthorized access,
  destructive database changes, or security findings affecting production.
- Escalate after one failed self-healing cycle, repeated external reachability
  alarms, an unavailable production database, or a failed rollback.
- For a nightly sync failure, preserve the run URL and error. Confirm whether
  real-time sync continued. Rerun only after you understand the failure, then
  reconcile Attio and PostgreSQL.
- If no alert arrived for a confirmed incident, treat alert delivery itself as
  impaired and verify SNS subscriptions and chat authorization.
