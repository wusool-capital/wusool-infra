# Monitoring and incident response

Toolkit logs are kept in CloudWatch for 30 days. Infrastructure alarms
publish to SNS topics, which reach email and, through AWS Chatbot, a Slack
alerts channel. Confirm the live subscriptions during handover: the repository
can't prove that recipients accepted them.

## Alarms

| Alarm | Fires when | Goes to | Automatic action |
| --- | --- | --- | --- |
| Toolkit not in service | No healthy instance for two minutes | Email and Slack | A replacement instance is launched |
| Toolkit unreachable | Route 53's HTTPS check of `/health` fails three times | **Slack only** (its topic is in `us-east-1`, with no email) | None |
| Toolkit high CPU | Above 85% for 15 minutes | Email and Slack | None |
| Toolkit watchdog recovery | The host watchdog restarted the stack or rebooted the host after three failed `/health` probes | Email and Slack | The watchdog already did the restart; find out why it was needed |
| Toolkit app logs silent | The app wrote no log line for 10 minutes | Email and Slack | None |
| Lead email send failed | An email fails after SES's own retries, at least once in 5 minutes | Email and Slack | The sweeper tries again later |
| Nightly Attio resync failed | The production workflow run fails, including when no Toolkit instance is running | Email and Slack | None |
| Nightly Attio resync heartbeat | No successful run for 30 hours, for example the workflow is disabled or never starts | Email and Slack | None |
| GuardDuty finding | Severity 4 or higher | **Email only** | None |
| Security Hub finding | High or critical | **Email only** | None |

An unhealthy Toolkit container is restarted automatically by an `autoheal`
container on the instance. A systemd watchdog on the host also probes `/health`
through Caddy every 30 seconds. After three misses it restarts the stack.
After ten in a row (about five minutes) it reboots the host, at most once an
hour. The watchdog alarm reports both. The Toolkit container is capped at
1.2 GB of memory, so a runaway Chromium is killed instead of starving the
host.

Slack shows repeat alerts for the same alarm as thread replies, which don't
notify by default. Turn on "Get notified about all replies" for the alerts
channel, or a second alert can be missed.

## What isn't alarmed

These only appear in logs, so someone must look for them:

- lead-tool runs abandoned by the sweeper (`lead_magnet_run_abandoned`);
- report code emails that fail to send;
- failed Sanity or Webflow syncs, and bad Sanity webhook signatures;
- failed Attio writes from the lead tools, including person and deal writes;
- the RDS database: there are no RDS alarms at all.

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

Use the matching runbook in `docs/runbooks/`: Toolkit outage,
Attio sync failure, database and migration failure, deployment failure, or
Google access for the interactions engine.
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
