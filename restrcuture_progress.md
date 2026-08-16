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
| 2 | `wusool-prod-infrastructure-alerts` has **zero subscriptions** while two CloudWatch alarms publish to it. Dev's is stuck `PendingConfirmation`. | **OPEN** |
| 3 | No backups of any kind: zero EBS snapshots, zero AWS Backup plans, zero DLM policies. | **PARTIALLY ADDRESSED** — see below |
| 4 | `N8N_ENCRYPTION_KEY` never set explicitly, so no backup could have restored n8n credentials. | **RESOLVED** |
| 5 | GuardDuty + Security Hub enabled but **zero EventBridge rules** — findings route nowhere. | **OPEN** |
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

## Open items, in priority order

1. **Defect 1 — the landmine is still armed.** Until the corrective
   `-target` apply runs, invoking the prod bootstrap document takes production
   down, and that invocation is the documented recovery procedure.
   **Freeze notice has not been announced.**
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
