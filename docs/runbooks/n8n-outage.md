# Incident: n8n unavailable or workflow execution failure

## Purpose

Recover the self-hosted n8n service running behind Caddy on its environment-
specific EC2 instance.

## Impact

n8n editor, API, and workflow webhooks may be unavailable. A workflow can also
reach n8n and fail later at an external-service node.

## Symptoms

- The environment n8n URL does not serve HTTPS successfully.
- The deployment health check cannot obtain HTTP 200 from `/healthz`.
- n8n execution history shows a failed node or credential error.
- CloudWatch shows an EC2 status or sustained CPU alarm.
- Caddy access logs show no request, or n8n/container logs show an internal
  failure.

## Severity

P1

## Immediate Actions

1. Record environment, UTC time, affected webhook or execution ID, and recent
   deployment without copying credentials or workflow data.
2. Check the environment URL: `https://n8n-dev.wusoolcapital.com/` for dev or
   `https://n8n.wusoolcapital.com/` for prod.
3. Check the matching GitHub Actions deployment, CloudWatch alarms, and the
   n8n CloudWatch log group for the same time window.

## Diagnosis

1. Confirm whether the failure is before n8n (DNS/Caddy), in n8n, or inside a
   workflow node.
2. For a missing or invalid HTTPS response, verify the Cloudflare DNS record,
   Elastic IP, certificate status, Caddy access logs, and Docker Compose
   container health. Live Cloudflare state and certificate ownership are NOT
   VERIFIED by this repository.
3. For a reached webhook, inspect n8n execution history and the completed nodes
   for external side effects before retrying.
4. Use the n8n stack outputs to identify `instance_id`, `n8n_url`, and
   `bootstrap_document_name`. Use Systems Manager rather than SSH; SSH is not
   enabled by default.
5. For an application or configuration change, compare the current stack
   module/template with the reviewed source. The old production re-provisioning
   procedure is explicitly stale.

## Recovery

1. For a transient container failure, use Systems Manager to inspect or restart
   the affected Docker Compose service after confirming the target instance.
2. For a configuration/image deployment failure, re-run the current
   OpenTofu-managed bootstrap document only through a reviewed deployment or
   rollback plan.
3. If the host is impaired, allow the documented infrastructure recovery path
   or execute a reviewed infrastructure change. n8n state is stored on the
   instance's persistent Docker volume; a replacement does not prove that the
   data was restored.
4. Retry a workflow only after confirming its idempotency and external side
   effects are safe.

## Validation

- The environment n8n URL returns successfully and the deployment health check
  receives HTTP 200 from `/healthz`.
- The editor and a safe webhook test work.
- The affected execution succeeds without duplicate external side effects.
- CloudWatch logs and alarms return to normal.

## Rollback

Restore the previously verified n8n image/configuration through a reviewed
source revert and OpenTofu plan. No verified n8n data backup or generic data
rollback mechanism was found.

## Escalation

Escalate for any missing persistent data, certificate/DNS ownership issue,
repeated host failure, failed rollback, or workflow retry with uncertain side
effects. The n8n owner, Cloudflare owner, and backup/recovery owner are NOT
VERIFIED in this repository.

## Do Not

- Do not delete Docker volumes or recreate the instance as a first response.
- Do not retry a non-idempotent workflow without reviewing its side effects.
- Do not use the stale bootstrap/re-provisioning instructions without comparing
  them to the current module template.

## Root Cause Follow-Up

Preserve the execution ID, node error, Caddy/container logs, deployment SHA,
and alarm timeline. Record whether the failure was DNS, TLS, host, container,
n8n, or an external dependency.
