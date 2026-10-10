# Operations and handover

This section is the engineering runbook for operating the Wusool platform.
Start with [Environments and access](environments-and-access.md), then use the
procedure for the task or incident at hand.

| Need | Page |
| --- | --- |
| Identify an environment or obtain access | [Environments and access](environments-and-access.md) |
| Release or reverse a change | [Deployment and rollback](deployment-and-rollback.md) |
| Respond to an alert or outage | [Monitoring and incident response](monitoring-and-incidents.md) |
| Understand or restore protected data | [Backups and recovery](backups-and-recovery.md) |
| Find the responsible system or supplier | [Ownership and service dependencies](ownership-and-dependencies.md) |
| Check what is delivered or still open | [Delivery status and open items](delivery-status.md) |

Step-by-step incident runbooks live in the repository under `docs/runbooks/`.
They cover a Toolkit outage, an n8n outage, Attio sync failure, database and
migration failure, and deployment failure. After an incident, follow
`docs/postmortems/README.md`.

## Operating principles

- Make infrastructure changes through source control and OpenTofu. Record any
  emergency console change in code as soon as service is restored.
- Use AWS Systems Manager for server access. SSH is closed and the database is
  private.
- Keep runtime secrets in AWS Secrets Manager. Never put a secret value in an
  issue, chat message, log excerpt, or this documentation.
- Treat a green infrastructure apply as incomplete until the health check
  passes.
- Preserve evidence during an incident: environment, UTC time, affected
  workflow, deployment run, alarms, and the relevant log window.

This documentation describes what the repository defines. It can't prove the
live state of AWS, GitHub, Slack, Attio, Sanity, Webflow, SES, Cloudflare, or
n8n. Confirm live state before a production change.
