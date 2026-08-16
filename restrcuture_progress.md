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
| 2 | `wusool-prod-infrastructure-alerts` had **zero subscriptions** while two CloudWatch alarms published to it. | **RESOLVED for prod** 2026-08-16; dev still pending confirmation |
| 3 | No backups of any kind: zero EBS snapshots, zero AWS Backup plans, zero DLM policies. | **PARTIALLY ADDRESSED** — see below |
| 4 | `N8N_ENCRYPTION_KEY` never set explicitly, so no backup could have restored n8n credentials. | **RESOLVED** |
| 5 | GuardDuty + Security Hub enabled but **zero EventBridge rules** — findings route nowhere. | **ROUTED** 2026-08-16; delivery pending subscription confirmation |
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

**`wusool-security-alerts` subscription is `PendingConfirmation`** — a third
email needing a click, or security findings still reach nobody.

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
1b. **Two subscriptions still `PendingConfirmation`** — `wusool-dev-infrastructure-alerts`
   (4 alarms) and `wusool-security-alerts` (all GuardDuty/Security Hub findings).
   Both need a click on the email to `raoof@azmora.ai`. Prod infra alerts are
   **confirmed**.
2. **Defect 6 — nothing is enforced.** `prod` now exists and will start
   receiving merges, with no branch protection, no required checks, and all
   merge methods enabled. Needs GitHub Team (~$32/mo at 8 seats) and repo admin.
3. **Defect 2 + 5 — alerting and security findings reach nobody.** One
   EventBridge rule plus a confirmed SNS subscription fixes both.
4. **Defect 3 — no recurring backups.** Phase H3 decision outstanding.
5. **Toolchain not yet standardized** (Phase A) — `.terraform-version` still
   claims Terraform 1.9.8; CI still installs the wrong tool.
6. **`main` not yet retired.**

## Decisions still outstanding

- Phase H3: AWS Backup plan vs DLM policy vs defer.
- Scribe ownership: adopt as `stacks/scribe`, or keep external with a documented
  contract.
- Who holds repo admin, and whether the org will move off the free plan.
