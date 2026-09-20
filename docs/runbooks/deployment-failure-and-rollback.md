# Incident: Production deployment failure or unsafe release

## Purpose

Recover a failed GitHub Actions deployment for Toolkit, n8n, or OpenTofu-managed
infrastructure.

## Impact

A release may leave the previous version running, register new infrastructure
without rolling the app, fail before migration, or serve an unhealthy service.

## Symptoms

- `Deploy prod` fails in build, OpenTofu apply, migration, bootstrap, or health
  verification.
- OpenTofu reports success but Toolkit `/health` or n8n `/healthz` is not 200.
- A migration fails before the Toolkit rollout.
- The plan proposes replacement, deletion, or unexpected IAM/network/database
  changes.

## Severity

P1 — Treat destructive changes, data loss, or security impact as P0.

## Immediate Actions

1. Stop reruns. Capture branch, commit SHA, workflow URL, first failing step,
   environment, and affected service.
2. Check whether the failure partially applied infrastructure or a database
   migration.
3. Check service logs and health endpoints before changing anything else.

## Diagnosis

1. Review the workflow in this order: image build/ECR, changed-stack detection,
   OpenTofu apply, database migration, SSM bootstrap/rollout, and health checks.
2. A successful OpenTofu apply only registers the SSM bootstrap document; it
   does not prove the app rolled out. Require the explicit health check.
3. For Toolkit, verify `/health`, `/readiness`, and `/embed.js`; for n8n,
   verify `/healthz` at the environment URL.
4. If the first failure is database-related, use
   [database-and-migration-failure.md](database-and-migration-failure.md).
5. If the first failure is service-specific, use
   [toolkit-outage.md](toolkit-outage.md) or
   [n8n-outage.md](n8n-outage.md).

## Recovery

1. For a transient workflow/SSM failure, correct the identified transient
   condition and rerun only after reviewing the failed invocation.
2. For a bad Toolkit application release, identify the last known-good image
   digest from a successful deployment or the production ECR repository.
3. From `infrastructure/terraform/stacks/toolkit`, initialize the production
   backend using the repository's documented backend key, create a reviewed
   OpenTofu plan with the known-good `image_digest`, and apply that plan only
   after human review.
4. For n8n or infrastructure, revert the responsible source change and deploy
   the reviewed OpenTofu plan through the matching branch/workflow. Restore a
   previously verified n8n image digest where applicable.
5. After recovery, fix or revert the source change so the next deployment does
   not reintroduce the incident.

## Validation

- The workflow completes through rollout and health verification.
- Toolkit `/health` and `/readiness` return HTTP 200; `/embed.js` returns 200
  when lead tools are in scope.
- n8n `/healthz` returns HTTP 200 when n8n is in scope.
- The intended user flow succeeds and no unrelated resource changed.

## Rollback

Toolkit rollback is by reviewed known-good ECR digest. n8n/infrastructure
rollback is by source revert and reviewed OpenTofu plan. There is no verified
generic database rollback; see the database runbook before reverting an app
that depends on a changed schema.

## Escalation

Escalate for any plan proposing replacement/deletion, partial migration,
failed rollback, missing image digest, or repeated failed workflow. Production
has no verified manual approval gate, so the operator must provide the review
checkpoint.

## Do Not

- Do not repeatedly rerun a failed apply.
- Do not run Terraform; this repository uses OpenTofu.
- Do not apply a production plan without reviewing replacement, deletion, IAM,
  network, and database changes.
- Do not force-push or change production configuration as an emergency shortcut.

## Root Cause Follow-Up

Record the failing stage, commit/image digest, plan summary, SSM invocation,
health results, and why the release escaped pre-production checks.
