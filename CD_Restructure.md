# Repo-wide maintainability foundation: migration plan

## Context

This repo (`wusool-infra`) has grown organically across five workstreams —
Terraform/n8n, CRM sync (Attio↔Postgres), Bedrock AI, the database schema,
and now matching-engine — each added by whoever needed it, with no shared
convention for testing, CI, deployment, or state isolation.

A direct survey of every non-Terraform directory (this session), cross-checked
against **live AWS data pulled via the `wusool` CLI profile** (not just
`PROGRESS.md`'s claims — one of them turned out to be stale, corrected
below), turned up concrete, verified recurring failures, not hypothetical
risk:

- **Correction to a claim in `PROGRESS.md`/§18, verified live**: prod is
  *not* Terraform-orphaned. `terraform/environments/prod`'s state
  (`tofu state list`) correctly tracks the real running
  `wusool-prod-n8n` instance (`i-0087f9ecb02462b2e`, `eu-central-1`,
  private IP `10.20.1.96`) — a commit on 2026-07-04 already fixed the
  region default from `me-central-1` to `eu-central-1`, after the
  PROGRESS.md note claiming the mismatch was written. `terraform plan`
  against the real backend (with the correct `terraform.tfvars` values —
  see below) shows **zero destructive changes**: `Plan: 0 to add, 2 to
  change, 0 to destroy`.
- **The real, verified risk is narrower but still live**: `terraform.tfvars`
  for prod is gitignored and not present in this checkout — only
  `terraform.tfvars.example` is committed. A real `terraform plan` run
  without the exact right values (confirmed by testing it both ways) shows:
  - Without the correct `n8n_webhook_url`, it plans to revert prod's live
    domain to an auto-generated `sslip.io` fallback.
  - **Even with the *correct* `n8n_webhook_url` matching the live domain**
    (`https://n8n.wusoolcapital.com/`, per `terraform.tfvars.example` and
    PROGRESS.md's 2026-08-10 cutover), the plan *still* shows a change to
    `module.n8n.aws_ssm_document.bootstrap`: the registered document's
    embedded script (currently `document_version = 4`) hardcodes the old,
    retired `n8n-prod.wusoolcapital.com` domain in its `docker-compose.yml`/
    `Caddyfile` heredocs — stale relative to what the *current* `.tpl`
    template would generate for the same real inputs. This is the exact
    "SSM document drifted from source template" bug §18 describes, now
    reproduced and confirmed directly via a real plan rather than inferred
    from a past incident report.
  - Net effect: applying prod today with the right tfvars would be a safe,
    *corrective* update (bringing the registered document back in line with
    reality) — but applying it with a wrong or missing `n8n_webhook_url`
    would be actively destructive to the live domain/webhook config, and
    there is no committed record of the correct value to check against.
- **The same class of SSM-document-drift bug has recurred three separate
  times on prod n8n** (documented in §18, not re-verified live beyond the
  above),
  each time via the same mechanism: the registered SSM bootstrap document
  holds an *embedded copy* of `user_data.sh.tpl` frozen at the last
  `terraform apply`. Every time it's re-run (e.g. to pick up a Secrets
  Manager change), it regenerates `docker-compose.yml`/`Caddyfile` from that
  stale embedded script and silently reverts live fixes — documented in
  §18 of the infrastructure overview (task-runner launcher config dropped
  twice; dual-domain Caddyfile dropped once). The matching-engine module
  built this session (`terraform/modules/matching-engine-ec2`) has the
  *identical* structural weakness: `local.user_data_rendered` and `git_ref`
  are baked into `aws_ssm_document.bootstrap.content` at apply time.
- **Zero automated CI/testing outside matching-engine.** `n8n`, `crm-sync`,
  `bedrock-ai`, and `database` are 100% PowerShell, run manually from
  Windows, with no lint config, no test framework, and no CI coverage at
  all — `.github/workflows/terraform-ci.yml` only checks Terraform
  fmt/validate. matching-engine is the only service with `ruff`/`ty`/`pytest`.
- **One Terraform state per environment, holding every service** — already
  identified and deliberately deferred in the matching-engine deploy plan
  (approved separately; referenced as Phase 3 below).
- **Database migrations are flat numbered SQL files with no tracking
  table** — idempotency relies entirely on `CREATE ... IF NOT EXISTS` being
  used consistently, and it isn't (`005_meetings.sql` lacks the guard;
  documented in `database/README.md` as a known, unfixed gap).
- **A branch-naming inconsistency**: `CONTRIBUTING.md` mandates PRs into
  `dev`, but the GitHub remote's default branch is `main`. This directly
  matters here — `matching_engine_git_ref` (added this session) defaulted
  to `"main"`, silently wrong relative to the repo's actual working
  convention.
- Two documentation-sync skills already exist and work well
  (`.agents/skills/sync-terraform-docs`, `.agents/skills/sync-project-docs`)
  — this plan extends their scope as each phase lands, it does not replace
  them.

Given explicit authorization to move/break/replace anything in service of a
maintainable foundation, this plan is sequenced by **actual risk to the live
production system first**, then cheap/no-risk foundational gates, then the
larger structural work — not by what's most interesting to build. Each phase
below states what breaks (or keeps silently breaking) if it's skipped.

## Phase 0 — Correct and commit prod's real config, then apply once to fix the drift

**Why first**: prod's Terraform state is fine (verified live) — but there is
currently no committed source of truth for the exact values a safe
`terraform apply` against prod needs, and the registered SSM document is
already provably stale relative to the current template. Any deploy workflow
(including the one already approved for matching-engine, if a `prod` path is
ever added for another service) is unsafe until this gap is closed —
not because applying would create a duplicate stack, but because applying
with the *wrong* values would silently revert the live domain/webhook
config, exactly as has already happened three times per §18.

1. **Recover and commit the real prod values.** Someone with access to
   however `terraform.tfvars` currently exists (a teammate's machine, a
   password manager, CI secrets — its location is itself unknown, which is
   its own finding) must confirm the exact values in use, especially
   `n8n_webhook_url = "https://n8n.wusoolcapital.com/"` (verified as the
   correct current value against live plan output and PROGRESS.md's
   2026-08-10 cutover) and `alert_email`. Non-secret values (region, CIDR,
   webhook URL, instance type, timezone) belong in a **committed**
   `terraform.tfvars` or equivalent (e.g. GitHub Actions `environment`
   variables once Phase 3's pattern extends to n8n) — they are
   configuration, not secrets, and their absence from version control is
   exactly how this drift went unnoticed. Only truly sensitive values
   (none currently exist in prod's `terraform.tfvars.example` — `key_name`
   is empty, `ssh_cidr_blocks` is empty) need to stay out of git.
2. **Run one real, careful `terraform plan` with the recovered values**,
   confirm it shows `0 to add, 0 to destroy` and only the expected
   `~ update in-place` on `aws_ssm_document.bootstrap` (regenerating it to
   match the current template/current real domain) — this was verified
   live this session and is the actual, current diff. Have a second person
   review the plan output before applying, given this is a live
   financial-services production system.
3. **Apply it once**, which corrects the stale SSM document at the source
   — closing out the specific instance of the §18 bug already reproduced.
   This does not, by itself, stop it from recurring on the *next* drift;
   that's what Phase 3's "regenerate-and-re-register as part of every
   deploy" invariant is for, extended to n8n.

**What breaks if skipped**: the exact bug from §18 keeps recurring —
whoever next needs to touch prod (a Secrets Manager rotation, a Terraform
change, anything requiring a bootstrap re-run) has no committed record of
the correct values, and the safest available fallback (re-run the existing
stale SSM document via `send-command`, as has been done three times) is
itself the mechanism that caused the last three incidents.

## Phase 1 — Fix what's cheap and load-bearing right now

No risk, no dependencies on anything else, should land before or alongside
Phase 0:

- **Resolve the branch inconsistency.** Confirm with the team whether `dev`
  or `main` is the actual integration branch going forward, then make
  `CONTRIBUTING.md`, the GitHub remote's default branch, `terraform-ci.yml`'s
  trigger branch, and `matching_engine_git_ref`'s default all agree. (The
  already-approved matching-engine deploy plan assumed `dev` based on
  `CONTRIBUTING.md`'s stated convention — confirm that's still current
  before relying on it.)
- **Fix `database/sql/005_meetings.sql`'s missing `IF NOT EXISTS` guard** —
  a one-line-class fix, already flagged in `database/README.md`, currently
  blocking any full schema re-run of `setup-postgres.ps1`.
- **Fix `README.md`'s stale "matching-engine is a placeholder" line** —
  false since this session, and directly misleading for anyone reading the
  repo structure to understand what's deployable from here.
- **Fix `terraform/modules/n8n-ec2/user_data.sh.tpl`'s single-hostname
  Caddyfile templating** — the root cause of one of the three recurring
  prod bugs in §18, straightforward to generalize to a list of hostnames.

**What breaks if skipped**: nothing dramatic, but each is a small, known,
already-diagnosed paper cut that costs real time every time someone hits it
again (as §18 shows happening more than once for the same root cause).

## Phase 2 — Baseline CI for the PowerShell workflows

Recommendation, not a question to put to the user: **keep PowerShell** for
`n8n`/`crm-sync`/`bedrock-ai`/`database` — everything there is already
Windows-oriented (`-NoProfile -ExecutionPolicy Bypass` throughout), and
porting to Python to match matching-engine's tooling would be a large,
user-invisible rewrite that consumes this plan's entire budget for no real
maintainability gain. Instead:

- Add **PSScriptAnalyzer** as a new, path-filtered GitHub Actions job
  (`.github/workflows/powershell-lint.yml`), triggered on `pull_request`
  for changes under `workflows/**/scripts/**` and `database/*.ps1` — mirrors
  `terraform-ci.yml`'s existing fmt/validate pattern, just for PowerShell.
  This is the first real CI coverage any of these scripts have ever had.
- Add **Pester tests only where a script is genuinely dangerous** — not a
  blanket test-everything mandate:
  - `database/setup-postgres.ps1`'s `-Reset` path.
  - `workflows/crm-sync/scripts/sync-postgres.ps1`'s `-Apply` path.
  These are the two places a bug silently corrupts or destroys real data;
  everything else (dry-run/read-only scripts like `validate-attio.ps1`,
  `validate-postgres.ps1`) is lower priority.
- matching-engine already has `ruff`/`ty`/`pytest` wired locally — add the
  equivalent as a path-filtered `.github/workflows/matching-engine-ci.yml`
  (currently nothing runs these in CI at all, only locally, per this
  session's own verification steps).

**What breaks if skipped**: the dangerous-path scripts (`-Reset`, `-Apply`)
stay one typo away from real data loss/corruption with no safety net beyond
manual review, and matching-engine's test suite can silently regress
without anyone noticing until a live Slack bug surfaces it (as has already
happened once this session).

## Phase 3 — Deploy workflows (matching-engine)

Already fully planned and approved separately this session — referenced
here for sequencing, not repeated in full. Summary: OIDC federation (no
static AWS keys), `terraform-plan.yml` (plan-on-PR),
`deploy-matching-engine-infra.yml` (`-target`-scoped apply as a stated
bridge until Phase 4), and `deploy-matching-engine-app.yml` (SSM redeploy,
no Terraform involved).

**Trigger model correction (superseding the earlier "manual-dispatch-only"
requirement, per a later decision this session)**: both deploy workflows
keep `workflow_dispatch` (so they can always be re-run on demand, with the
`environment` input still a manual choice), **and** gain a `push` trigger
scoped to the branch that maps to each environment — a push/merge to `dev`
auto-triggers the dev deploy with `environment: dev` pre-selected; a push/
merge to the production branch auto-triggers the prod path (once one
exists for a given service) with `environment: prod` pre-selected. Both
paths funnel through the same job, gated the same way — GitHub Environment
protection rules (required reviewers) are what make even the push-triggered
prod path require an actual human approval before `apply` runs, not the
trigger type. This does not change Phase 0's requirement to fix prod's
config drift first, nor Phase 4's per-service state plan — it only changes
*what causes the workflow to start*, never what it's allowed to touch.

Branch↔environment mapping depends on Phase 1's branch-naming resolution
(`dev`-vs-`main`) — confirm which branch is genuinely prod-track before
wiring the prod push trigger for any service.

**One correction to apply when implementing that plan, given this session's
fuller findings**: the SSM-document-goes-stale bug pattern from §18 is not
n8n-specific — it's a structural property of "bake a script into an SSM
document at `terraform apply` time." State this as an explicit invariant
going forward, for every service that uses this pattern (matching-engine
now, n8n eventually): **the bootstrap document must be re-registered from
current source as part of every deploy, and a deploy workflow must never
allow "re-run the existing document" as its only path** — which is
already true for `deploy-matching-engine-app.yml`'s design (it calls
`ssm send-command` against whatever document Terraform's *last apply*
registered — so an app-only redeploy still can't pick up a `.tpl` change
without a Terraform apply first; document this limitation explicitly rather
than letting it become bug #4 of the same species).

**Also apply the same fix to n8n**, once Phase 3's pattern is proven on
matching-engine: give `n8n-ec2` the same "regenerate + re-register the SSM
document, then invoke it" GitHub Actions workflow, instead of the current
ad hoc "SSH/console + manually re-run stale document" process — this is
the single change most likely to stop the exact bug that's hit prod three
times.

## Phase 4 — Per-service Terraform state split

Already scoped as "Deferred" in the matching-engine deploy plan — summary:
split `terraform/environments/dev/main.tf`'s one shared state into a base
layer (network, SNS, CloudTrail/GuardDuty/SecurityHub, shared secrets
container) plus one root module per service, each with its own backend key,
reading the base layer via `terraform_remote_state`. Migrate
matching-engine first (fewest inbound dependencies — nothing else in dev
depends on it yet). Do this **after** Phase 0/1 land, since touching shared
state safely requires the environment to already be well-understood and
low-risk to `terraform plan` against.

**What breaks if skipped**: every future "deploy service X" workflow either
needs its own `-target` bridge (workable but explicitly discouraged by
HashiCorp for routine use) or risks reconciling unrelated pending changes
elsewhere in the same shared state.

## Phase 5 — Database migration tracking

Add a `schema_migrations` tracking table (applied filename + timestamp) so
`setup-postgres.ps1` stops depending on every SQL file being perfectly
`IF NOT EXISTS`-idempotent to be safely re-run — record what's actually
been applied, skip already-applied files, and make a partial/failed apply
diagnosable instead of silently order-dependent. This is additive, not a
full migration-tool adoption (no Alembic/Flyway) — matches the repo's
existing "plain numbered SQL files" convention, just makes re-runs safe.

## Ongoing — extend the existing doc-sync skills, don't replace them

`sync-terraform-docs` and `sync-project-docs` already do real, working
documentation-reconciliation. As each phase above lands:
- Phase 0/4 changes should trigger `sync-terraform-docs` (Terraform
  topology changed).
- Phase 1/2/3/5 changes should trigger `sync-project-docs` (new CI, new
  workflows, new scripts, `PROGRESS.md` update) — including recording this
  plan's phases as a new workstream once execution begins.

## Verification (per phase, at execution time — not part of this plan-writing pass)

- Phase 0: with the recovered/committed values, `terraform plan` against
  prod shows `0 to add, 0 to destroy`, only the `aws_ssm_document.bootstrap`
  in-place update — confirmed reproducible this session via
  `tofu plan -var 'n8n_webhook_url=https://n8n.wusoolcapital.com/' ...`.
  After apply, confirm `n8n_url` output still resolves to the live domain
  and the site still serves HTTPS correctly.
- Phase 1: `setup-postgres.ps1` runs twice in a row without error (proves
  005's guard fix); `terraform-ci.yml` still passes; grep confirms no
  remaining "placeholder" claim about matching-engine in `README.md`.
- Phase 2: a deliberately-bad PowerShell change fails `powershell-lint.yml`;
  a deliberately-bad matching-engine change fails `matching-engine-ci.yml`.
- Phase 3: per the already-approved matching-engine deploy plan's own
  verification section.
- Phase 4: `terraform plan` in the split-out matching-engine state shows no
  drift immediately after migration; dev's n8n/postgres continue running
  unaffected.
- Phase 5: re-running `setup-postgres.ps1` against a fully-migrated database
  applies zero files and reports "up to date," instead of erroring on 005.
