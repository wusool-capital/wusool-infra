# Operations and handover

This section is the engineering runbook for operating the delivered Wusool
platform. Start with [Environments and access](environments-and-access.md),
then use the procedure for the task or incident at hand.

| Need | Runbook |
| --- | --- |
| Identify an environment or obtain access | [Environments and access](environments-and-access.md) |
| Release or reverse a change | [Deployment and rollback](deployment-and-rollback.md) |
| Respond to an alert or outage | [Monitoring and incident response](monitoring-and-incidents.md) |
| Understand or restore protected data | [Backups and recovery](backups-and-recovery.md) |
| Find the responsible system or supplier | [Ownership and service dependencies](ownership-and-dependencies.md) |
| Check what is delivered or still open | [Delivery status and open items](delivery-status.md) |

## Operating principles

- Make infrastructure changes through source control and OpenTofu. Record any
  emergency console change in code immediately after service is restored.
- Use AWS Systems Manager for server access. The repository does not enable SSH
  ingress by default, and the databases are not public.
- Store runtime secrets in AWS Secrets Manager. Never place secret values in an
  issue, chat message, log excerpt, or this documentation.
- Treat a green infrastructure apply as incomplete until the service health
  check passes.
- Preserve evidence during an incident: note the environment, UTC time,
  affected workflow, deployment run, alarms, and relevant log window.

This documentation describes repository-defined behavior. A repository review
cannot prove the current state of AWS, GitHub, Slack, Attio, Cloudflare, or n8n;
operators should confirm live state before a production change.
