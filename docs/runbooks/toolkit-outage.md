# Incident: Toolkit outage or unhealthy service

## Purpose

Recover the deployed Wusool Toolkit service: the FastAPI/Slack Bolt process
that also serves the desktop API and website lead tools.

## Impact

Slack commands, Attio webhook processing, WusoolScribe submissions, and lead
tool requests may fail. A live `/health` response does not prove PostgreSQL is
reachable; use `/readiness` for that distinction.

## Symptoms

- Toolkit public `/health` does not return HTTP 200.
- `/readiness` or `/ready` returns HTTP 503.
- Slack reports connection errors or commands do not acknowledge.
- CloudWatch reports Toolkit container health, external `/health`, CPU, or
  in-service-instance alarms.

## Severity

P1 — Treat suspected credential exposure, unauthorized access, or confirmed data
corruption as P0 and escalate immediately.

## Immediate Actions

1. Record environment, UTC start time, affected surface, recent deployment run,
   and the exact error without copying customer data or secrets.
2. Check both `/health` and `/readiness` from the environment's Toolkit URL.
3. Check the matching GitHub Actions deployment and CloudWatch alarm/log window.
4. If the ASG is replacing the only instance, allow one replacement cycle to
   complete while monitoring; do not repeatedly redeploy.

## Diagnosis

1. Confirm AWS identity with the verified command `aws sts get-caller-identity`.
2. From the repository root, inspect the live Toolkit stack outputs using the
   production or development backend procedure in
   `gitbook/operations-and-handover/environments-and-access.md` and
   `infrastructure/terraform/README.md`. The Toolkit stack exposes
   `app_urls`, `ssm_instance_id`, `bootstrap_document_name`, and
   `autoscaling_group_name`.
3. If the public health check fails, distinguish host replacement, container
   health, and public reachability using the Toolkit CloudWatch logs and alarms.
4. If `/health` is 200 but `/readiness` is 503, continue with
   [database-and-migration-failure.md](database-and-migration-failure.md).
5. If only Slack fails while HTTP health is normal, inspect Slack request
   routing and signing-secret configuration with the Slack administrator;
   repository evidence does not verify the live Slack configuration.

## Recovery

1. For a transient unhealthy container, use Systems Manager on the current
   instance to restart the affected Docker Compose service, with human review
   of the target instance and command.
2. For a failed or suspect release, follow
   [deployment-failure-and-rollback.md](deployment-failure-and-rollback.md).
3. For a missing instance, verify the ASG replacement and SSM registration
   before taking further action. The Toolkit instance is ASG-managed and has
   no stable instance ID.

## Validation

- Toolkit `/health` returns HTTP 200.
- Toolkit `/readiness` returns HTTP 200 with `{"status":"ready"}`.
- `/embed.js` returns HTTP 200 when lead tools are in scope.
- A safe affected user flow succeeds and CloudWatch errors stop increasing.

## Rollback

Use the last known-good Toolkit ECR image digest through the reviewed procedure
in [deployment-failure-and-rollback.md](deployment-failure-and-rollback.md).

## Escalation

Escalate after one failed self-healing cycle, two failed recovery attempts, a
missing SSM-online instance, repeated health failures, or any security/data
integrity concern. Route to the AWS/Toolkit owner; named owners are not
verified in this repository.

## Do Not

- Do not expose SSH or PostgreSQL publicly to restore service.
- Do not copy Secrets Manager values, `.env.production`, tokens, or customer
  payloads into tickets or logs.
- Do not edit mirrored PostgreSQL records directly to fix an application symptom.

## Root Cause Follow-Up

Capture the failing deployment, instance ID, alarm, log window, and recovery
action. Confirm the ASG, container health, SSM, and alert path behaved as
configured.
