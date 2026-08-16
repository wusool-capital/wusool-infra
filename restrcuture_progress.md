# Restructure progress log

Running record of what has actually been **done**, as distinct from what is
*planned* (`Final_restructure_plan.md`) or *handed over*
(`SCRIBE_INFRA_CONTRACT.md`).

AWS account `030179310793`, region `eu-central-1` (state bucket in
`me-central-1`). Every fact here was read from AWS or produced by a real
command — nothing is inferred from repo documentation.

---

## Session 1 — 2026-08-15 / 2026-08-16

### Investigation (read-only)

Surveyed the live account and both Terraform states. Findings that contradicted
repo documentation:

| Claim in repo | Reality |
|---|---|
| `PROGRESS.md`: prod is Terraform-orphaned | **False.** `wusool/prod/terraform.tfstate` (serial 13) tracks `i-0087f9ecb02462b2e`. Migration is a `state mv`, not an import campaign. |
| Backend region `me-central-1` looks wrong | **Correct as-is.** Bucket really is in `me-central-1`; resources in `eu-central-1`. Intentional. |
| `.terraform-version` = 1.9.8 (Terraform) | State written by **Terraform 1.15.6**; only **OpenTofu 1.12.5** installed. Verified OpenTofu reads that state fine — `0 to destroy`, zero `forces replacement`. |
| `CD_Restructure.md` verification claims | Unreliable — superseded and deleted. |

Also established: no ECR repositories, no IAM OIDC provider,
`/wusool/prod/matching-engine` does not exist, `sg-0684b8cf83abfd065` is
`wusool-scribe-instance`, and `wusool-scribe` is a fourth deployed service
(c6a.xlarge, **in the dev VPC**, managed from a state outside this repo).

### Six defects found

| # | Defect | Status |
|---|---|---|
| 1 | Prod SSM bootstrap document hardcodes the **retired** `n8n-prod.wusoolcapital.com`. Invoking it — the documented recovery procedure — takes production offline. | **OPEN — armed** |
| 2 | `wusool-prod-infrastructure-alerts` had **zero subscriptions** while two CloudWatch alarms published to it. | **RESOLVED** 2026-08-16 — all three topics confirmed |
| 3 | No backups of any kind: zero EBS snapshots, zero AWS Backup plans, zero DLM policies. | **PARTIALLY ADDRESSED** — see below |
| 4 | `N8N_ENCRYPTION_KEY` never set explicitly, so no backup could have restored n8n credentials. | **RESOLVED** |
| 5 | GuardDuty + Security Hub enabled but **zero EventBridge rules** — findings route nowhere. | **RESOLVED** 2026-08-16 — routed and subscribed |
| 6 | GitHub org on **free** plan with a private repo → no branch protection, no rulesets, all merge methods enabled, operator is not repo admin. None of the plan's guardrails are enforceable. | **OPEN** |

### Changes actually made to AWS

**1. n8n encryption keys extracted and stored** *(resolves Defect 4)*

Extracted from the live instances via SSM and verified **byte-for-byte** against
each running container's `~/.n8n/config`:

| Secret | Verified |
|---|---|
| `/wusool/prod/n8n-encryption-key` | matches `i-0087f9ecb02462b2e` (32 chars) |
| `/wusool/dev/n8n-encryption-key` | matches `i-02ed4b390b677518b` (32 chars) |

Both are **new** secrets — no existing secret was modified.

*Caveat:* the key transited SSM command output, retained by AWS ~30 days. The
instance role holds only `GetSecretValue` so it could not write the secret
itself. Purging that command history is worth considering.

*Still to do:* wire `N8N_ENCRYPTION_KEY` into the bootstrap so it stops being
generated-and-forgotten. Simplest route is adding it under the `env` object of
`/wusool/<env>/n8n`, which the existing bootstrap already expands into
environment variables — **no template change required**. The value must be
identical to the stored one or every existing credential breaks.

**2. Deleted the unused DynamoDB lock table**

`wusool-tfstate-locks` (`me-central-1`). Verified before removal: zero
references in dev, prod **or scribe** state, and its single item was a stale
digest record (`wusool-tfstate/wusool/dev/terraform.tfstate-md5`, no `Info`
attribute → not a live lock) left from before backends moved to
`use_lockfile = true`. `me-central-1` now has no DynamoDB tables; state remains
readable. Code references in `terraform/bootstrap/` still to be removed (§D0a).

**3. Pre-restructure EBS snapshots** *(partially addresses Defect 3)*

All four running instances, 160 GiB total. First-ever snapshots in this account,
so these are full copies rather than incremental.

| Instance | Volume | Snapshot |
|---|---|---|
| `wusool-prod-n8n` (`i-0087f9ecb02462b2e`) | `vol-0943ab2f832103df1` (50 GiB) | `snap-049bd02b9774a8f4e` |
| `wusool-dev-n8n` (`i-02ed4b390b677518b`) | `vol-054cbc3d97fd264a1` (30 GiB) | `snap-0470a29009ad43a92` |
| `wusool-dev-matching-engine` (`i-0fb853edb9f185db9`) | `vol-0f8cacfc7aa1e7238` (30 GiB) | `snap-0077ca44b219f38a7` |
| `wusool-scribe` (`i-01bf509a92ed1dcba`) | `vol-036e2cd738497b785` (50 GiB) | `snap-0f28a587eb9c37f97` |

All tagged `Purpose=pre-restructure-backup`. **These cover the restructure window
only — they are not a backup policy.** Defect 3 stays open until a recurring
AWS Backup plan or DLM policy exists (Phase H3, still undecided).

### Changes made to the repo

Branch `plan-cd-restructure`:

| Commit | What |
|---|---|
| `ffcc812` | Replace `CD_Restructure.md` with `Final_restructure_plan.md` (verified against live AWS) |
| `9e75917` | Fix seven execution blockers found in review |
| `3bcdf60` | Record squash-to-dev / merge-to-prod strategy |
| `8800687` | Rename prod branch, add branch-creation steps |
| `d1a10a3` | Record unrouted security findings (Defect 5) |
| `9d9c01e` | One merge builds, applies and rolls per environment |
| `15eb7a6` | Document three hotfix paths |
| `befa104` | Record unenforceable guardrails (Defect 6) |
| `2561250` | Rename prod branch from `app` to `prod` |
| `3e90147` | Extract `SCRIBE_INFRA_CONTRACT.md` |

**Not pushed.** `CD_Restructure.md` was deleted (staged in `ffcc812`).

### Changes made to GitHub

- Created branch **`prod`** at `6d780743` (identical to `dev`; zero divergence
  both directions).
- Deleted branch **`app`** after confirming its commit was reachable from both
  `dev` and `prod`.
- Default branch is **`dev`** *(set by the user)*.
- `main` still exists at `cf09f59e` — **stale and structurally obsolete** (no
  `database/` or `workflows/`). §C0a has tag-then-delete commands.

---

## Session 2 — 2026-08-16

### Phase A — toolchain standardized on OpenTofu *(commit `f419dc1`)*

- `terraform/.terraform-version` → **`terraform/.opentofu-version`**, pinned **1.12.5**.
- `required_version` → `>= 1.12.0` in all three roots.
- CI swapped `hashicorp/setup-terraform` → **`opentofu/setup-opentofu`**.
  **Job names changed** (`Terraform Format` → `OpenTofu Format`), so the
  required-status-check names in `CONTRIBUTING.md` changed with them.
- All three `.terraform.lock.hcl` regenerated → provider source is now
  `registry.opentofu.org/hashicorp/aws`, same version `5.100.0`.
- `CONTRIBUTING.md`: new Toolchain section, `tofu` in all examples, corrected
  the `Azmora-ai` → `wusool-capital` remote URL.
- Verified: `tofu fmt -check` clean, all three roots validate.

### n8n module hardening *(uncommitted at time of writing)*

Running images were captured from the live boxes first, because **dev and prod
run different versions** (dev n8n **2.26.8**, prod **2.27.5**) — a shared default
would have silently changed dev.

| Change | Why |
|---|---|
| `additional_hostnames` (list) + `local.caddy_hostnames` | Caddyfile was single-hostname — root cause of a prior prod incident. Renders identically when the list is empty. |
| `local.user_data_rendered` | `templatefile()` was called **twice** with identical inputs — two places to drift. Now one render reused by both `aws_instance` and `aws_ssm_document`. |
| `n8n_image` / `runners_image` / `caddy_image` — **required, digest-validated** | `n8nio/runners` publishes **no stable version tags**, only `latest` and nightlies **including a v3 line**, so a restart could have pulled a v3 runner against 2.x n8n. |
| `docker-compose-linux-$(uname -m)` | `ami_architecture` accepted `arm64` while the URL hardcoded x86_64. |
| **`N8N_RUNNERS_AUTH_TOKEN` preserved across re-runs** | Bug found while verifying: `cat > n8n.env` **truncates the file**, so the `grep -q` idempotency guard always missed and a **new token was minted on every bootstrap run**. Now captured before truncation and restored. |

### Defects 1 + 2 — prod corrective apply **DONE**

State backed up to `.state-backups/prod-2026-08-16-0734.tfstate`; pre-apply S3
version `AuUozBZeZhas_7gpMr1XSsYIt9GvwL2t`.

```
Plan: 1 to add, 2 to change, 0 to destroy   (forces replacement: 0)
Apply complete! Resources: 1 added, 2 changed, 0 destroyed.
```

**Verified after apply:**

| Check | Result |
|---|---|
| SSM document version | 4 → **5** |
| Retired `n8n-prod.wusoolcapital.com` in registered doc | **0 occurrences** (was 3) — **Defect 1 disarmed** |
| Live `n8n.wusoolcapital.com` | 2 occurrences (`N8N_HOST`, `WEBHOOK_URL`) + Caddyfile site block |
| `https://n8n.wusoolcapital.com` | `/healthz` 200, `/` 200, `/signin` 200 |
| n8n version | **2.27.5 — unchanged** |
| Workflows | **"Tally Buyer to Attio" and "Tally Seller to Attio" both reactivated** — credentials decrypted, proving the encryption key survived |
| Task runners | `launcher-javascript` + `launcher-python` registered |
| `database.sqlite` | 6.9 MB, intact; `config` (encryption key) present |
| On-box images | all three digest-pinned as intended |

**Correction to what was predicted:** the apply was described as runtime-inert
("`user_data` only executes at boot"). **That was wrong.** The
`aws_ssm_association` attached to the document **re-ran it automatically** when
the document updated, executing the bootstrap and recreating all three
containers. Prod took a brief outage (~80s instance modification plus container
start) that had been explicitly ruled out beforehand. Outcome was clean and the
fix is live on the box, but the prediction was incorrect and the approval was
given on that basis.

**Defect 2 is NOT closed.** The SNS subscription was created but sits at
`PendingConfirmation` — `raoof@azmora.ai` must click the confirmation link.
Until then prod alarms still notify nobody. Dev's subscription is in the same
state.

### Defect 2 — prod alerting **CLOSED**

`raoof@azmora.ai` confirmed the prod subscription
(`…:4bd43d22-cd91-4002-a7a8-a2c0f2bbafd4`). Prod's two alarms now reach a human.
**Dev's subscription is still `PendingConfirmation`** and covers four alarms
(n8n + matching-engine) — still needs a click.

### Defect 5 — security findings now routed *(dev root, moves to stacks/account in Phase D)*

GuardDuty and Security Hub are **account-level singletons**, so their findings
belong to neither environment. They got a dedicated topic rather than borrowing a
per-env one — which also keeps "a box is unhealthy" separate from "someone may be
attacking us".

| Resource | Detail |
|---|---|
| `aws_sns_topic.security_alerts` | `wusool-security-alerts` |
| `aws_cloudwatch_event_rule.guardduty_findings` | GuardDuty, **severity ≥ 4** (MEDIUM+); LOW is mostly policy noise |
| `aws_cloudwatch_event_rule.securityhub_findings` | Security Hub, **HIGH/CRITICAL + Workflow NEW + RecordState ACTIVE** — unfiltered, the 14 LOW CIS findings would have become spam and the routing would be muted within a week |
| `aws_sns_topic_policy.security_alerts` | Lets `events.amazonaws.com` publish, scoped by `AWS:SourceAccount` |
| GuardDuty target | Input transformer produces a readable email rather than raw JSON |

**All three subscriptions CONFIRMED 2026-08-16.** For the first time in this
account, every alarm and every security finding terminates at a real inbox:

| Topic | Covers |
|---|---|
| `wusool-prod-infrastructure-alerts` | 2 prod alarms |
| `wusool-dev-infrastructure-alerts` | 4 dev alarms (n8n + matching-engine) |
| `wusool-security-alerts` | GuardDuty MEDIUM+, Security Hub HIGH/CRITICAL |

**Defects 2 and 5 fully closed.**

*Caveat:* Terraform state still records `pending_confirmation = true` for the two
that were confirmed after the apply. That attribute is only refreshed on the next
plan/apply and has no effect on delivery — SNS is the source of truth, and it
reports all three confirmed.

*Not yet delivered-tested:* the rules match and the topic has confirmed
subscribers, but no finding has actually arrived by email yet. GuardDuty
publishes on a `SIX_HOURS` cadence, so the first real end-to-end proof will come
with the next finding.

### Dev apply — the shared-state problem, demonstrated

The first dev plan showed `7 to add, 5 to change, **1 to destroy**`, where only
the 7 adds were the security routing. Investigation:

- `/wusool/dev/ddl-commands` created 2026-08-15 20:15 IST, **empty**
  (`VersionIdsToStages: null` — no value ever stored).
- Merged `origin/dev` (2 commits: #23, #25) and re-planned — **plan unchanged**,
  which is what settled it: #25 *deliberately* merged matching-engine and
  ddl-commands into one bot, so the separate secret is a genuine orphan, not
  someone's live work. The initial reading of it as "in-flight work" was wrong;
  merging dev was the right way to find that out.
- Applying also redeployed **#25's merged bot** to dev, because
  `module.matching_engine`'s `user_data` hash changed. That is a *feature
  deployment* riding along on an infrastructure change — exactly the coupling
  the per-service state split (Phase D) exists to remove. Proceeded knowingly;
  the feature was checkpointed.

```
Apply complete! Resources: 7 added, 5 changed, 1 destroyed.
```

State backed up first: `.state-backups/dev-2026-08-16-0747.tfstate`,
pre-apply S3 version `fVcePHDT_9HTUEFgZ.NtgJal1mEpQUlo`.

**Post-apply verification**

| Check | Result |
|---|---|
| EventBridge rules | both `ENABLED`, both targeting `wusool-security-alerts` |
| dev n8n | `/healthz` 200, **2.26.8 unchanged**, `database.sqlite` 19 MB intact, images digest-pinned |
| dev matching-engine | `matching-engine-app-1` **Up (healthy)**, `/health` 200, clean startup |
| `/wusool/dev/ddl-commands` | deleted 2026-08-16 (30-day recovery window) |

Both dev services restarted via the SSM association re-run — expected this time,
unlike the prod apply.

### Prod PostgreSQL created *(2026-08-16)*

**Decisions:** dedicated prod instance (never shared with dev), cheapest viable
sizing, **private subnet**, seeded from a dev snapshot so schema *and* data carry
over.

| Setting | Value |
|---|---|
| Instance | `wusool-prod-postgres`, `db.t4g.micro`, 20 GiB gp3 (autoscales to 100) |
| Network | new subnet `10.20.3.0/24` (`subnet-0b8b5c89d6aeaaa67`), **`publicly_accessible = false`** |
| Seed | restored from `wusool-dev-postgres-seed-20260816-0803` |
| Credentials | `manage_master_user_password = true` — RDS-managed and rotated |
| Protection | `deletion_protection = true`, final snapshot on delete, 7-day backups |
| Ingress | prod n8n SG (for the SSM tunnel runbook); matching-engine prod joins later |

Prod's network previously had **no database subnet** — `prod/main.tf` omitted
`database_private_subnet_cidr`, and the DB subnet group needs ≥2 subnets. Added
`10.20.3.0/24` to mirror dev's `10.10.3.0/24`.

Module change: `postgres-rds` gained `snapshot_identifier`. When set, `db_name`
and `username` are **omitted** (RDS rejects them — they come from the snapshot),
and `lifecycle { ignore_changes = [snapshot_identifier] }` prevents a later edit
from replacing the instance and destroying its data. Verified backward
compatible — dev planned **"No changes"** afterwards.

**Verified beforehand — prod n8n was NOT writing to the dev database.** The
concern was reasonable but the isolation holds: dev RDS ingress lists only three
SGs, all in the dev VPC; dev RDS is `publicly_accessible = false`; there is **no
VPC peering and no transit gateway**; and prod n8n's SQLite contains zero
credential types, zero references to `cpuwqesq4v8p`, and no RDS hostname at all.

#### Incident: interrupted apply left state and reality diverged

The `tofu apply` was killed by a **2-minute command timeout** while RDS creation
was still running (RDS takes 5–15 minutes). Consequences:

- AWS **did** create the subnet, route-table association, DB subnet group,
  security group and RDS instance — those API calls had already succeeded.
- Terraform recorded **none of them**: state stayed at serial 15.
- A `.tflock` object was left behind (lock ID `84c5ba08-…`).

A naive re-apply would have failed on duplicate identifiers (CIDR already in
use, DB identifier already exists). Recovery was `force-unlock` followed by
`tofu import` of each orphaned resource. Note the route-table association takes
`subnet_id/route_table_id`, **not** the `rtbassoc-…` ID.

**Lesson:** long-running creates (RDS, and anything else measured in minutes)
must be run so they cannot be interrupted — background the apply rather than
letting a foreground timeout kill it mid-flight. This is a real argument for the
CD workflows in Phase E, where `cancel-in-progress: false` exists precisely to
stop this.

#### Finding: snapshot restore silently defeats `manage_master_user_password`

Surfaced only because the RDS import failed on an output referencing
`master_user_secret[0]`, which was an empty list.

**A snapshot-restored instance inherits the snapshot's master credentials.**
`manage_master_user_password = true` is ignored at creation time, so the new prod
database came up with **`MasterUserSecret: null` and dev's master password**.
For a period, anyone with dev database credentials could log into prod.

This is not obvious from the Terraform config — the argument is present and
appears to be honoured. The only signal was `describe-db-instances` reporting a
null managed secret where dev had `active`.

**Fixed** by a follow-up `apply`, which issued a modify enabling
`manage_master_user_password`. RDS then generated a **distinct** managed secret:

| Env | Master secret |
|---|---|
| dev | `rds!db-e8bdd9d8-8f57-49c5-825a-6dc1f1416108` |
| prod | `rds!db-111ff9a9-d787-465d-8581-c71edb69ae3f` |

The same apply also set `max_allocated_storage = 100` (autoscaling) and
`skip_final_snapshot = false` with a final-snapshot identifier — neither of which
the restore had applied either.

**Generalise this:** any future snapshot-restored database needs an explicit
credential-rotation step. Restoring a database restores its *secrets*, not just
its data. Worth checking on the `matching-engine` prod database work too.

**Module output hardened:** `master_user_secret_arn` now uses `try(...)`, since
the attribute is legitimately empty on a freshly restored instance and the raw
index made `import` and `plan` fail outright.

### `/wusool/prod/matching-engine` created *(2026-08-16)*

`arn:…:secret:/wusool/prod/matching-engine-tIAhLJ`. Same key names as dev —
separation is by secret path, not variable prefix.

| Key | State |
|---|---|
| `database_url` | **populated**, verified pointing at `wusool-prod-postgres` and matching the current RDS-managed password |
| `env`, `github_token`, `slack_bot_token`, `slack_signing_secret` | **empty placeholders** |

Built by piping the RDS-managed secret straight into the new secret — the
password was never echoed to a terminal or a transcript.

**Deliberately matched dev's URL shape, including the absence of
`?sslmode=require`.** The app rewrites `postgresql://` to
`postgresql+asyncpg://`, and **asyncpg does not understand libpq's `sslmode`
parameter** — adding it would likely break startup. Do not "improve" this
without testing.

**Slack credentials added 2026-08-16** — `slack_bot_token` (59 chars) and
`slack_signing_secret` (32 chars) are populated from the separate prod Slack app.
`database_url` re-verified as pointing at prod afterwards.

> ⚠️ **Rotate these.** Both were pasted in plaintext into a chat transcript,
> which persists. The signing secret is what proves a request genuinely came
> from Slack, so anyone holding it can forge requests. They are not yet wired to
> anything, so rotating now is cheap: regenerate both in the Slack app config and
> update the secret via CLI/console rather than through chat.

**Still blocking a prod matching-engine deploy:**
- `github_token` — needed only while the bootstrap still does `git clone`.
  **Phase F's ECR work removes the need entirely**, so ECR should land before
  prod matching-engine rather than filling in a token that is then deleted.
- The app currently connects as the RDS **master** user (`wusool_admin`),
  matching dev. A least-privilege application role would be better for prod;
  raised, not actioned.

### 🔴 DEFERRED: rotate leaked dev credentials

A failed bootstrap ran under `set -x` and echoed **every dev secret in plaintext**
into SSM command history (retained ~30 days) and CloudWatch:

| Credential | Urgency |
|---|---|
| GitHub PAT `github_pat_11AGL35SQ0…` | **highest — repo write access** |
| Slack bot token (dev) `xoxb-11354073143281-…` | high |
| Slack signing secret (dev) `33660bc1ac51…` | high — allows forging requests |
| Dev RDS master password (inside `database_url`) | high |
| Firecrawl API key `fc-4fd7ae0588a0…` | medium |

**Cause fixed** in both `toolkit-ec2` and `n8n-ec2` templates: `set +x` before
any secret is read, verified live (trace now stops at `+ set +x`). **The
already-leaked values still need rotating** — user has deferred this.

Note the prod Slack credentials were separately pasted into a chat transcript
and also warrant rotation.

### Rename: matching-engine → toolkit *(2026-08-16)*

Everything renamed: module dir `terraform/modules/toolkit-ec2`, Terraform
addresses (`module.wusool_toolkit`), AWS resource names (`wusool-dev-toolkit-*`),
secrets (`/wusool/{dev,prod}/toolkit`), ECR (`wusool/toolkit`), on-box path
`/opt/toolkit`.

**URL deliberately unchanged.** `wusool_toolkit_public_url` is pinned to
`https://63-184-6-136.sslip.io` in dev tfvars. Left empty it would derive
`toolkit-63-184-6-136.sslip.io` from the app name and break the existing Slack
Request URL. Safe to hardcode because the IP is an Elastic IP.

**Three latent bugs found and fixed** — none caused by the rename; it merely
exercised code paths nobody had run before:

1. **SG rename deadlock.** A security group cannot be deleted while an ENI uses
   it or another SG references it. With a fixed `name` and default
   destroy-then-create ordering, renaming deadlocked: the old SG could not be
   deleted until the instance moved off it, and the instance could not move
   until the new one existed. Fixed with `name_prefix` +
   `create_before_destroy`. (SG names now carry a numeric suffix — expected.)
2. **`set -x` leaked every secret** — see above.
3. **`git checkout <branch>` fails on a shallow single-branch clone.** The
   initial clone is `--depth 1 --branch <ref>`, so its refspec tracks only that
   branch; `git checkout <other>` errors with "pathspec did not match" and
   `origin/<other>` never exists. **Changing `git_ref` on an existing instance
   was therefore impossible.** Fixed with `git checkout --detach FETCH_HEAD`.

**`git_ref` corrected `main` → `dev`.** Cloning the stale `main` branch (which
has no `workflows/wusool-toolkit/`) is what broke the bootstrap. Note this is a
**per-environment tfvars value — it does not switch automatically by
environment.** It should not reach prod at all: Phase F (ECR) removes `git clone`
entirely, so prod deploys a pinned image digest with no git ref and no
`github_token`.

### Prod RDS + secrets recap

- `wusool-prod-postgres` — private subnet `10.20.3.0/24`, seeded from dev
  snapshot, own RDS-managed credential (see the snapshot-restore finding above).
- `/wusool/prod/toolkit` — `database_url` (verified pointing at prod),
  `slack_bot_token`, `slack_signing_secret` populated. `github_token` empty and
  should stay that way if ECR lands first.
- **Prod does not yet instantiate the toolkit module** — prod has only `network`,
  `n8n` and `postgres`.

### Phase E — CI/CD workflows created *(2026-08-16)*

**GitHub OIDC live** — no static AWS keys anywhere.

| Resource | Purpose |
|---|---|
| `token.actions.githubusercontent.com` provider | trusts `repo:wusool-capital/wusool-infra:*` |
| `wusool-gha-plan` | ReadOnlyAccess + state read/write. Any branch — used by plan-on-PR |
| `wusool-gha-apply-dev` | PowerUser + scoped IAM. **Trust restricted to `refs/heads/dev`** |
| `wusool-gha-apply-prod` | PowerUser + scoped IAM. **Trust restricted to `refs/heads/prod`** |

Branch restriction is enforced by **AWS at AssumeRole time** via the OIDC `sub`
claim, not by workflow logic that could be edited in a PR. A workflow running on
`dev` cannot assume the prod role.

#### Workflow files

Separate dev and prod files by explicit request — the environment is *stated*,
never derived from `github.ref`, so a branch-detection mistake cannot point a
dev deploy at prod.

| File | Trigger | Behaviour |
|---|---|---|
| `deploy-dev.yml` | push to `dev` | build → deploy |
| `deploy-prod.yml` | push to `prod` | build → deploy |
| `_build.yml` | called by both | buildx `linux/amd64` → that env's ECR |
| `_deploy.yml` | called by both | apply → **poll bootstrap** → **verify health** |
| `terraform-plan.yml` | any PR | plan for the PR's **base** branch, posted as a comment |

#### 🔴 The deploy now verifies, rather than assuming

The single most valuable change in this phase. `tofu apply` returns success as
soon as the SSM document is **registered** — it does not wait for the bootstrap
to run. **Three separate broken deploys on 2026-08-16 reported
`Apply complete!`** (stale `main` branch; `git checkout` on a shallow clone; a
port conflict leaving Caddy in `Created`). In a pipeline each would have been a
green tick over a broken deploy.

`_deploy.yml` therefore does, after apply:

1. `ssm send-command` and capture the command id
2. poll until the status leaves `Pending`/`InProgress`
3. **fail the job** on anything but `Success`, printing `StandardErrorContent`
4. **poll `/health` until 200** — a successful bootstrap still leaves a
   container able to sit in `Created`
5. write `deployed_sha` **only after both pass** — recording it earlier would
   make a failed deploy look deployed to the next run's change detection

#### ECR: one repository per environment, both environments build

Superseding the earlier build-once/promote-the-digest design, by decision:

- `wusool-dev/toolkit` and `wusool-prod/toolkit` — **separate registries**, no
  cross-environment coupling.
- **Prod builds its own image**, exactly as dev does. This also removes the
  `HEAD^2` digest-resolution fragility of the promotion model — a squash merge
  into `prod` would have broken it outright.
- Both repos: `IMMUTABLE` tags, scan-on-push, keep last 30 images. `_build.yml`
  reuses an existing image when the tag is already present, since re-running a
  workflow on an unchanged commit would otherwise fail the push.

**Open trade-off:** with independent builds, prod's artifact is not guaranteed
byte-identical to what dev tested. `uv.lock` pins every Python dependency, but
the Dockerfile pins base images by **tag** — `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`
and `python:3.12-slim-bookworm` — and those move. **Pinning both by digest would
close the gap** while keeping full isolation. Not yet done.

#### Not yet working

- **No image in either ECR repository.** Two local `docker buildx --push`
  attempts failed on TLS handshake timeouts from this machine (see below); the
  first CI run will populate it.
- `_deploy.yml` references outputs that do not exist yet —
  `toolkit_bootstrap_document`, `toolkit_instance_id`, `toolkit_url` — and a
  `wusool_toolkit_image_digest` variable. These arrive with the module change
  that swaps `git clone` + `docker compose build` for an ECR pull by digest.
- Prod does not instantiate the toolkit module at all yet.

#### Local network unreliability — an argument for CI

Four separate AWS failures from this workstation today: a DNS lookup failure on
the state bucket mid-apply (which left state and reality diverged), two TLS
handshake timeouts pushing to ECR, and a DNS failure on
`monitoring.eu-central-1.amazonaws.com` that killed an apply outright. **None of
this affects GitHub Actions**, which is a further reason builds and applies
belong there rather than on a laptop.

### Phase D begins: `stacks/account` populated and live *(2026-08-16)*

First real `state mv` of the restructure, done and verified.

**Decision (ECR placement):** ECR now per-environment, so it moves with its
service into `stacks/toolkit` later, NOT into `stacks/account`. Account stack
holds only genuinely account-wide singletons: GuardDuty, Security Hub, the
security-alerts SNS+EventBridge routing, and GitHub OIDC (provider + 3 roles).

**Procedure:** `state pull` → `state mv` each of 23 addresses into a local
staging file (data sources included, for completeness) → `state push` the
staging file to `stacks/account`'s new backend → `state push` the
now-smaller state back to dev. Backup taken first:
`.state-backups/dev-pre-account-split-2026-08-16-0929.tfstate`.

**Verification — both stacks plan clean:**
```
dev:             No changes. Your infrastructure matches the configuration.
stacks/account:  No changes. Your infrastructure matches the configuration.
dev state:     61 resources (was 84)
account state: 24 resources
```

One deliberate, non-zero diff surfaced before the final apply: tags. Moved
resources dropped their stale `Environment=dev` tag and gained `Scope=account`;
`Owner` changed from `wusool-infra` to `platform` (the account stack's own
default). Zero destroys, zero replacements — reviewed and applied.

**`environments/dev/main.tf`**: 512 → 236 lines. GuardDuty/SecurityHub/
security-alerts and the entire OIDC block removed; `aws_ecr_repository` stays
(per the ECR decision above).

### What's still in `environments/` — the honest remainder of Phase D

`environments/` and `bootstrap/` are **not yet safe to delete.** Still owned by
`environments/dev` and `environments/prod` directly (not yet in any `stacks/`):

- `module.network`, `module.n8n`, `module.wusool_toolkit`,
  `module.wusool_toolkit_bedrock`, `module.bedrock`, `module.postgres`
- CloudTrail, the per-env SNS alerts topic, the n8n/toolkit secrets, ECR

Each needs the same treatment as today's account move: a `stacks/<name>`
scaffold, `state mv`, verify clean. `bootstrap/`'s code cannot be deleted until
the live `wusool-tfstate` bucket is imported into `stacks/account` (§D0a — not
yet done, since the bucket already exists and works, this is lower urgency than
it looks).

### `stacks/base` populated for dev AND prod *(2026-08-16)*

Same procedure as `stacks/account`: rewired both env roots to
`data.terraform_remote_state.base`, then `state mv` per-address, verified
`0/0/0`, pushed both sides.

| | dev | prod |
|---|---|---|
| Moved | 20 resources (network×11, SNS×2, CloudTrail×6, caller_identity) | 20 resources, identical shape |
| Backend key | `wusool/dev/base/terraform.tfstate` | `wusool/prod/base/terraform.tfstate` |
| Backup | `.state-backups/dev-pre-base-split-2026-08-16-0938.tfstate` | `.state-backups/prod-pre-base-split-2026-08-16-0947.tfstate` |

**Two indexing mistakes made and caught during this move** — both by validation
before anything touched real state: line-range deletion accidentally caught
`aws_secretsmanager_secret.n8n`/`.wusool_toolkit`'s **declarations** (not the
resources — those stayed correctly in AWS/state throughout, confirmed via
`tofu state list` each time) — recovered verbatim from `git show HEAD:...`.
**Lesson: recompute line ranges against the file's current state at edit time,
never reuse indices from an earlier grep in the conversation.**

**Also caught: `state push` does not compute outputs.** After pushing a stack's
state for the first time, its `outputs` block is empty until a `plan`/`apply`
actually runs — remote_state reads from a freshly-pushed stack fail with
"Unsupported attribute" until that happens. Each stack got a no-op
`0 added, 0 changed` apply specifically to populate outputs before the
consuming root was re-planned.

**Prod's post-migration plan surfaced two unrelated pending items**, bundled
into one reviewed apply after explicit confirmation (restarts prod n8n):
- `aws_ecr_repository`/`aws_ecr_lifecycle_policy` for `wusool-prod/toolkit` —
  pure addition, added to prod earlier this session, never applied.
- The `set +x` secret-leak fix (same class as the toolkit leak found earlier)
  — reaches prod's n8n bootstrap for the first time.

```
Apply complete! Resources: 2 added, 2 changed, 0 destroyed.
```

**Verified after:** `https://n8n.wusoolcapital.com/healthz` → 200 (3rd attempt,
~30s after restart); both workflows ("Tally Buyer to Attio",
"Tally Seller to Attio") reactivated; all 5 stacks (`environments/dev`,
`environments/prod`, `stacks/base`×2, `stacks/account`) plan **`No changes`**.

### Mid-flight data-safety audit *(user-requested, 2026-08-16)*

Full sweep before continuing: zero destructive commands (`docker compose
down -v`, `volume rm/prune`, `rm -rf` on data paths, `tofu destroy`,
`-replace`, `taint`) across every module, both env roots, all stacks, all
workflow files. RDS defaults confirmed safe
(`deletion_protection=true`, `skip_final_snapshot=false`,
`ignore_changes=[snapshot_identifier]` correctly placed on the `aws_db_instance`
resource — re-verified after catching my own earlier misplacement of this exact
block on the wrong resource). Both EC2 modules retain
`ignore_changes=[ami]`. Docker volume names are fixed literals, unaffected by
redeploys. One standing, already-documented, not-new risk: `_deploy.yml` runs
`apply -auto-approve` with no plan-review gate — the accepted risk from
declining the prod approval gate (*Accepted risks* item 0).

### `stacks/n8n` and `stacks/toolkit` populated (dev); `stacks/n8n` for prod *(2026-08-16)*

Same `state mv` discipline throughout — backup, extract, verify `0/0/0`,
push both sides, populate outputs, re-plan. All clean.

| Stack | dev | prod |
|---|---|---|
| `stacks/n8n` | ✅ 18 resources | ✅ 16 resources |
| `stacks/toolkit` | ✅ 20 resources (incl. ECR) | not yet created — prod has no toolkit instance yet |

`module.bedrock`/`module.wusool_toolkit_bedrock` became `module.bedrock[0]` in
both new stacks (`count = var.enable_bedrock ? 1 : 0`), so a toggle exists per
environment instead of the bedrock module being unconditionally created.

#### 🔴 Real bug caught by verification: cross-stack variable name collision

`stacks/n8n` and `stacks/toolkit` both declared a generic `instance_type`
variable. Since both read the **same shared** `envs/dev.tfvars`, n8n's
`t3.small` silently leaked into toolkit's plan — the post-migration plan
proposed resizing the toolkit box (t2.micro → t3.small) with **nobody having
asked for that**. This is exactly why the original monolithic root prefixed
toolkit-specific variables (`wusool_toolkit_instance_type`) — a convention
dropped when scaffolding the new stacks.

**Fixed properly, not patched**: renamed to `toolkit_instance_type` with a
comment explaining why, and audited every other shared variable name between
the two stacks for the same risk. Confirmed safe by checking live values:
`root_volume_size` (both real instances are 30 GiB — shared default is
correct), `ami_architecture`/`ssh_cidr_blocks`/`web_cidr_blocks`/`key_name`
(genuinely identical intent in the original design).

**General lesson recorded**: any stack sharing a flat `envs/*.tfvars` file with
another stack must give its non-globally-shared variables a distinct name.
OpenTofu does not error on unrecognized `-var-file` keys (verified — only a
suppressible warning), so a collision fails **silently** into a wrong value,
not a loud error. This must be checked by hand for `stacks/postgres` next.

**Also recovered**: `wusool_toolkit_public_url` (pinned to the bare-IP
hostname per an explicit earlier request) had never been copied into
`envs/dev.tfvars` — caught by the same diff-before-apply discipline before
it could silently rewrite the live Caddy vhost and break the Slack Request URL.

### 🔴 Flagged, not yet fixed: CD workflows still target the directory being deleted

`deploy-dev.yml`/`deploy-prod.yml` (written earlier, before the stacks split)
apply `terraform/environments/${{ inputs.environment }}`. That directory is
being dismantled by this exact phase and is the explicit deletion target once
migration finishes. **Once it's gone, those workflows have nothing to apply.**
Must be rewritten to target `terraform/stacks/*` (a matrix per stack, per the
plan's original E4 design) before `environments/` can safely be deleted.
Surfaced by direct user question, not caught proactively — should have been
anticipated when the stacks split began.

### Snapshot status

| Snapshot | State |
|---|---|
| `snap-049bd02b9774a8f4e` prod n8n | **completed** (before the apply) |
| `snap-0077ca44b219f38a7` dev matching-engine | **completed** |
| `snap-0470a29009ad43a92` dev n8n | **completed** |
| `snap-0f28a587eb9c37f97` scribe | **completed** |

All four completed before the dev apply.

Note: `aws ec2 wait snapshot-completed` exited 0 while `describe-snapshots` still
reported two as `pending`. Trust `describe-snapshots`, not the waiter.

---

## Open items, in priority order

1. ~~Defect 1 — the landmine~~ **RESOLVED 2026-08-16.** Document v5 carries the
   live hostname; the freeze can be lifted. Recurrence prevention (re-register
   from source on every deploy) still depends on Phase E.
1b. ~~SNS subscriptions pending~~ **RESOLVED 2026-08-16** — all three topics
   confirmed. Alerting and security findings now reach a real inbox.
2. **Defect 6 — nothing is enforced.** `prod` now exists and will start
   receiving merges, with no branch protection, no required checks, and all
   merge methods enabled. Needs GitHub Team (~$32/mo at 8 seats) and repo admin.
3. **Defect 2 + 5 — alerting and security findings reach nobody.** One
   EventBridge rule plus a confirmed SNS subscription fixes both.
4. **Defect 3 — no recurring backups.** Phase H3 decision outstanding.
5. ~~Toolchain not standardized~~ **DONE** — OpenTofu 1.12.5 pinned, CI swapped
   to `opentofu/setup-opentofu`, lockfiles regenerated.
6. **`main` not yet retired.**

## Decisions made 2026-08-16

- **Separate Slack app for prod** — not shared with dev. Requires a second Slack
  app registration (bot token, signing secret, slash commands, request URL)
  before the prod matching-engine stack is applied.
- **Separate RDS instance for prod**, with matching-engine attached. Blocked on
  `stacks/base` prod gaining a **database subnet** — prod's network omits
  `database_private_subnet_cidr` today, and the DB subnet group needs ≥2 subnets.
  Suggested `10.20.3.0/24` to mirror dev's `10.10.3.0/24`.
- **Secret naming stays path-based** (`/wusool/<env>/<service>`) with identical
  key names across environments — no `DEV_`/`PROD_` variable prefixes, so app
  code is environment-agnostic and prod credentials never sit on a dev box.

## Decisions still outstanding

- Phase H3: AWS Backup plan vs DLM policy vs defer.
- Scribe ownership: adopt as `stacks/scribe`, or keep external with a documented
  contract.
- Who holds repo admin, and whether the org will move off the free plan.
