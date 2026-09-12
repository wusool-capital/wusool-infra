# Deployment and rollback

Application and infrastructure delivery is automated by GitHub Actions. A push
to `dev` deploys development; a push to `prod` deploys production. Both can also
be started manually. Production currently has no manual approval gate.

The pipeline builds a Toolkit image, publishes it to that environment's ECR
repository, applies changed OpenTofu stacks in dependency order, runs pending
database migrations, deploys by immutable image digest, and verifies service
health. n8n must return HTTP 200 from `/healthz`; Toolkit must return HTTP 200
from `/health`. Lead-tool smoke checks also run when applicable.

## Standard deployment

1. Review the pull request checks and the OpenTofu plan. Investigate unexpected
   replacement, deletion, network, IAM, or database changes before merging.
2. Merge into `dev` and watch `Deploy dev` through build, apply, migration,
   rollout, and health checks.
3. Exercise the changed workflow in development and inspect errors and logs.
4. Promote the reviewed change to `prod`, then watch `Deploy prod` to completion.
5. Verify the affected user flow and service health in production. Record the
   deployment run and result in the release or delivery record.

**Expected outcome:** the workflow is green, health endpoints return 200, and
the changed workflow succeeds in the intended environment.

**If deployment fails:** do not repeatedly rerun a failed apply. Read the first
failing step, check whether infrastructure or a migration partially completed,
and inspect the service logs. A failed migration blocks application rollout.
Escalate database migration failures to the application/database owner and any
unexpected resource destruction to the infrastructure owner.

## Roll back Toolkit application code

1. Identify the last known-good production image digest from a successful
   deployment or ECR. Confirm it belongs to the production repository.
2. From `infrastructure/terraform/stacks/toolkit`, initialize the production
   backend and create an OpenTofu plan using the production variable file and
   the known-good `image_digest` override.
3. Review the plan. It should change the deployed application version without
   replacing unrelated infrastructure.
4. Apply that reviewed plan, then wait for Toolkit `/health` and the affected
   user flow to succeed.
5. Revert or fix the source change so the next branch deployment does not
   immediately restore the bad version.

**Expected outcome:** the known-good digest is running and health checks pass.

Database migrations require a separate compatibility decision. The repository
automatically applies forward migrations but contains no generic automated
database rollback. Do not downgrade the application if the old version is
incompatible with the migrated schema; use a forward fix or a reviewed recovery
plan with the database owner.

## Roll back infrastructure or n8n

Revert the responsible source change, review a fresh OpenTofu plan, and deploy
the revert through the matching branch. n8n images are pinned in environment
configuration, so rollback means restoring a previously verified digest and
applying the reviewed plan.

The production n8n re-provisioning procedure is marked stale in the existing
handover. Do not use an old bootstrap document as an emergency rollback without
first comparing it with the current module template. Escalate if a plan proposes
RDS replacement, state changes, or deletion; those require a specific recovery
plan rather than a routine rollback.
