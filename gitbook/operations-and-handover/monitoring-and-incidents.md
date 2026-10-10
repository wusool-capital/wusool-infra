# Monitoring and incident response

Toolkit and n8n logs are kept in CloudWatch for 30 days. Infrastructure alarms
publish to SNS topics, which reach email and, through AWS Chatbot, a Slack
alerts channel. Confirm the live subscriptions during handover: the repository
can't prove that recipients accepted them.

## Alarms

| Alarm | Fires when | Goes to | Automatic action |
| --- | --- | --- | --- |
| Toolkit not in service | No healthy instance for two minutes | Email and Slack | A replacement instance is launched |
| Toolkit unreachable | Route 53's HTTPS check of `/health` fails three times | **Slack only** (its topic is in `us-east-1`, with no email) | None |
| Toolkit high CPU | Above 85% for 15 minutes | Email and Slack | None |
| Lead email send failed | An email fails after SES's own retries, at least once in 5 minutes | Email and Slack | The sweeper tries again later |
| n8n status check | A failed check for two minutes | Email and Slack | None |
| n8n high CPU | Above 85% for 15 minutes | Email and Slack | None |
| Nightly Attio resync failed | The production workflow run fails | Email and Slack | None |
| GuardDuty finding | Severity 4 or higher | **Email only** | None |
| Security Hub finding | High or critical | **Email only** | None |

An unhealthy Toolkit container is restarted automatically by an `autoheal`
container on the instance; this isn't an alarm.

## What isn't alarmed

These only appear in logs, so someone must look for them:

- lead-tool runs abandoned by the sweeper (`lead_magnet_run_abandoned`);
- report code emails that fail to send;
- failed Sanity or Webflow syncs, and bad Sanity webhook signatures;
- failed Attio writes from the lead tools, including person and deal writes;
- the RDS database: there are no RDS alarms at all;
- failed n8n workflows, which appear only in n8n's execution history.

The nightly resync only runs in production. Development has no mirror to
check: its database is a hand-seeded sandbox.

## Incident procedure

1. Record the environment, start time in UTC, affected users and workflows,
   recent deploys, and the exact error. Keep customer data out of the record.
2. Confirm scope with the health endpoint and one safe user-flow check.
3. Check GitHub deploy and nightly-sync history for a related failure.
4. Read the CloudWatch alarms and logs for the same window. For the Toolkit,
   tell apart a replaced instance, a restarted container, and an unreachable
   endpoint; each needs a different response.
5. Restore service with the smallest reversible step: let self-healing
   finish, restart the container through Systems Manager, or roll back.
6. Verify health and the user flow, watch for recurrence, and record the
   resolution and follow-up owner.

Use the matching runbook in `docs/runbooks/`: Toolkit outage, n8n outage,
Attio sync failure, database and migration failure, or deployment failure.
After resolving an incident, write a postmortem following
`docs/postmortems/README.md`.

## Escalation guidance

- Escalate at once for suspected credential exposure, unauthorized access,
  destructive database changes, or a security finding affecting production.
- Escalate after one failed self-healing cycle, repeated unreachable alarms,
  an unavailable production database, or a failed rollback.
- **Nightly resync failure:** keep the run URL and error, and check whether
  the real-time webhook carried on. Rerun only once you understand the
  failure, then reconcile Attio and PostgreSQL.
- **Lead email alarm:** find the log event and whether the visitor
  confirmation or team notice failed. Check the configured sender and
  recipient and SES delivery status. Don't recreate the lead; it is already in
  Attio.
- **No alert for a real incident:** treat alerting itself as broken and check
  the SNS subscriptions and Chatbot authorization.
