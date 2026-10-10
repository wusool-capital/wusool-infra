# n8n

## What it does

n8n is the self-hosted workflow automation service. This repository manages its
AWS runtime: networking, secrets, logs, and task runners. Workflows,
credentials, executions, and users live inside n8n and are managed through its
own interface.

## Components

The n8n stack creates one EC2 instance per environment. It has an encrypted
GP3 root disk, an Elastic IP, a security group, and an instance profile. Logs
go to a CloudWatch log group kept for 30 days. The stack itself adds a Secrets
Manager secret and Bedrock access, in both environments. IMDSv2 is required.

Docker Compose runs:

- `n8n`, with its persistent named volume;
- `task-runners`, for JavaScript and Python Code nodes; and
- Caddy, which obtains HTTPS certificates and proxies to n8n.

Port 5678 is only exposed between containers, never published on the host.
The security-group rule for it has no effect.

## Access

- Administration uses Systems Manager. SSH is closed in both environments.
- DNS must point at the Elastic IP before Caddy can get a certificate.
- The public interface is the environment's HTTPS URL: the editor, the API,
  and workflow webhooks. There is no Wusool-specific API in front of it.

## Data flow

Users and webhook callers reach Caddy over HTTPS, and Caddy forwards to n8n.
Workflows call their own configured services with credentials stored in n8n.
Code nodes run in the separate runner container. All state lives in Docker
volumes on the instance.

## Upgrades

1. Change the image digest in the environment's `tfvars` file. Tags are
   rejected; images must be pinned by digest. The AMI is pinned too.
2. The deploy workflow applies the stack, runs the bootstrap SSM document to
   recreate the containers on the same volume, and checks `/healthz`.
3. Test the editor, webhooks, stored credentials, and both kinds of Code node.

## Monitoring

- CloudWatch collects cloud-init and Caddy access logs.
- Two alarms go to the base stack's alert topic: a failed status check for
  two minutes, and CPU above 85% for 15 minutes.
- These only describe the host. Failed workflows appear in n8n's own
  execution history.

## Backups

**There is no backup of n8n data.** No snapshot, AWS Backup plan, or export
covers the instance volume, so losing it loses every workflow, credential, and
execution. Rebuilding the infrastructure doesn't restore any of that. Adding a
snapshot schedule is an open handover item.

## Failure behavior

- Containers restart automatically; bootstrap retries a failed container
  recreation three times.
- When a webhook execution fails, record the execution ID and check
  completed nodes for side effects before retrying.
- If a webhook never reaches n8n, check DNS, Caddy logs, and container
  health before changing the workflow.

Runbook in the repository: `docs/runbooks/n8n-outage.md`.

## Code

`infrastructure/terraform/stacks/n8n` and
`infrastructure/terraform/modules/n8n-ec2`.
