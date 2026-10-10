# Deployment and rollback

GitHub Actions deploys the server and infrastructure. A push to `dev` deploys
development and a push to `prod` deploys production; both can also be run by
hand. **Production has no manual approval gate.**

Only changes under `server/`, `infrastructure/terraform/`, or the workflows
trigger a deploy. Changes to `sanity/`, `scribe-desktop/`, or `gitbook/` never
deploy anything; they have their own release steps below.

## What a deploy does

1. **Build** the Toolkit image and push it to the environment's ECR
   repository. Production builds its own image; it never promotes dev's.
2. **Detect changes.** Each stack records the commit it last deployed. Only
   stacks with changes since then are applied; a workflow or shared `tfvars`
   change applies every stack.
3. **Base**, if changed.
4. **n8n**, if changed: apply, run the bootstrap SSM document (two attempts of
   up to 15 minutes), then poll `/healthz`.
5. **Toolkit**: apply with the new image digest, which only *registers* a new
   bootstrap document.
6. **Migrate**: run `alembic upgrade head` on the Toolkit instance through
   SSM, with two attempts. A failed migration stops the deploy before the new
   version is rolled out.
7. **Roll out**: run the bootstrap document, which pulls the new image and
   restarts the container.
8. **Check**: poll `/health`, then check that `/embed.js` returns 200.
9. **PostgreSQL**, if changed, last.

A stack's deployed commit is recorded only when its steps succeed. Deploys
are never cancelled midway.

## Checks before merging

- Pull requests to `dev` and `prod` must pass the database schema check,
  which runs `./checks.sh schema` against a disposable PostgreSQL.
- `terraform-ci` validates all seven stacks, and `terraform-plan` comments
  plans on the pull request.
- Locally, run `./checks.sh` from `server/` as described in the repository's
  contributor guide.

## Standard deployment

1. Review the pull request checks and the OpenTofu plan. Investigate any
   unexpected replacement, deletion, network, IAM, or database change.
2. Merge into `dev` and watch `Deploy dev` to completion.
3. Exercise the changed workflow in development and check the logs.
4. Promote to `prod` and watch `Deploy prod` to completion.
5. Verify the affected user flow in production, and record the run.

**If a deploy fails:** don't rerun a failed apply repeatedly. Read the first
failing step, check whether infrastructure or a migration partly completed,
and inspect the logs. See `docs/runbooks/deployment-failure-and-rollback.md`.

## Roll back the Toolkit

**Preferred:** revert the bad commit and push it to the branch. The normal
deploy rebuilds and rolls out the previous code, and keeps change detection
consistent.

**Fast path, when a revert can't wait:**

1. Find the last known-good production image digest from a successful deploy
   run or ECR.
2. In `infrastructure/terraform/stacks/toolkit`, plan and apply with the
   production variables **and** `-var=image_digest=<known-good digest>`.
   Production's `tfvars` holds an all-zero placeholder digest, so a plan
   without the override would point at an image that doesn't exist.
3. The apply only registers the bootstrap document. Run it on the instance
   with `aws ssm send-command`, using the stack's `bootstrap_document_name`
   output, and wait for the command to succeed.
4. Check `/health` and the affected user flow.
5. Revert the source too, or the next deploy brings the bad version back.

Migrations only go forward; there is no automatic database rollback. Don't
run old code against a schema it doesn't understand. Use a forward fix or a
recovery plan agreed with the database owner.

## Roll back n8n or infrastructure

Revert the change, review a fresh plan, and deploy through the branch. For
n8n, rollback means restoring the previous image digest in the environment's
`tfvars`. As with the Toolkit, applying only registers the bootstrap document,
and the deploy then runs it. Escalate any plan that proposes replacing RDS,
changing state, or deleting resources.

## Stacks applied by hand

`account`, `peering`, and `scribe-updates` span environments, so no deploy
applies them. An operator plans and applies them from their stack folders
after review.

## Release WusoolScribe

1. Bump the version in the three files the workflow checks.
2. Run the `scribe-release` workflow, choosing the `stable` channel. The app
   only reads stable, so a beta release reaches nobody.
3. The workflow builds for Apple silicon, signs the update, uploads it and
   `latest.json`, and invalidates CloudFront.

**Roll back** by restoring the previous version of `latest.json` in the update
bucket, which keeps old versions for 90 days, then invalidating CloudFront.

## Release the Sanity Studio

The Studio deploys from `sanity/` with `npx sanity deploy`. Each environment
needs a Sanity webhook pointing at its `/reports/webhooks/sanity` endpoint,
signed with the secret held in that environment's Toolkit secret. The Studio
README has the full setup.
