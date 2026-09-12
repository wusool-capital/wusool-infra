# n8n

## Purpose

n8n is the self-hosted workflow automation service. This repository manages
its AWS runtime, networking, secrets injection, logs, and task runners.
Workflow definitions, credentials, executions, and users live inside n8n and
are administered through its own authenticated interface.

## Components

The environment-specific OpenTofu stack creates one EC2 instance with an
encrypted GP3 root disk, Elastic IP, security group, IAM instance profile,
Secrets Manager secret, CloudWatch log group, and status/CPU alarms. Docker
Compose runs:

- `n8n`, with its persistent named volume;
- `task-runners`, with JavaScript and native Python runner configuration; and
- Caddy, which obtains HTTPS certificates and proxies to port 5678.

The instance role supports Systems Manager, CloudWatch, and access only to its
configured secret. Optional Bedrock permissions are attached by the stack.

## Data flow

Users and webhook callers connect over HTTPS to Caddy. Caddy forwards requests
to n8n. Workflows call their configured services using credentials stored by
n8n or supplied through the environment. Code nodes run in the external runner
container through n8n's task broker. Application and Caddy state persist in
Docker volumes on the instance.

## Dependencies and configuration

OpenTofu inputs set the hostname, webhook URL, time zone, image versions,
instance/disk size, network allowlists, optional hostnames, and alarm topic.
The environment secret may contain SMTP settings and an `env` map. Bootstrap
preserves the generated runner token and mounts a custom runner policy so the
configured Python stdlib/external-module settings reach the runner.

DNS must resolve to the Elastic IP before Caddy requests a certificate.
Administration should use Systems Manager; SSH is optional and explicitly
allowlisted. Port 5678 stays internal unless its exposure input is enabled.

## Interfaces

The public interface is the environment's HTTPS n8n URL, including n8n's
editor, API, and workflow webhooks. Exact webhook contracts belong to their
workflows inside n8n; there is no Wusool-specific REST facade.

Operators can trigger the OpenTofu-managed SSM bootstrap document to refresh
Compose configuration while preserving the volume. The stack outputs the URL,
instance identifier, security group, secret name, and SSM document name.

## Processing and failures

- Containers use `restart: always`; bootstrap retries transient Compose
  recreation failures three times.
- CloudWatch collects cloud-init and Caddy access logs. EC2 status and sustained
  high-CPU alarms notify the shared SNS topic when configured.
- Failed workflows and credential errors appear in n8n execution history; EC2
  alarms do not prove that every workflow succeeds.
- Workflow data lives on the instance volume. Infrastructure recreation alone
  does not prove that application data was restored.
- Upgrade validation must cover the editor, webhooks, stored credentials, and
  JavaScript/Python Code nodes.
