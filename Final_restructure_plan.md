# wusool-infra: CD restructure — execution plan

---

# 🔴 STOP — DO THIS FIRST, BEFORE ANY RESTRUCTURING

**Six defects, all verified live. Defect 4 is already resolved. Defects 1 and 2
are fixed by one apply; Defect 3 is a snapshot you take before touching
anything; Defect 5 is a small EventBridge rule that makes the existing security
tooling functional; Defect 6 is a GitHub plan limitation that must be resolved
before this plan's guardrails mean anything. None of the AWS-side items depend
on any other phase in this document.**

## Defect 1 — a command that takes production offline is armed right now

The registered prod SSM bootstrap document (`document_version = 4`, the latest)
embeds a base64 script that decodes to:

```
N8N_HOST=n8n-prod.wusoolcapital.com
WEBHOOK_URL=https://n8n-prod.wusoolcapital.com/
Caddyfile:  n8n-prod.wusoolcapital.com { reverse_proxy n8n:5678 }
```

The live domain is **`n8n.wusoolcapital.com`**. `n8n-prod.wusoolcapital.com` was
retired at the 2026-08-10 cutover.

Invoking that document rewrites the live Caddyfile and compose file to a retired
hostname and **takes production down**. That invocation is the *documented
recovery procedure* and has been used three times.

## Defect 2 — prod alarms notify nobody

Verified live: `wusool-prod-n8n-high-cpu` and `wusool-prod-n8n-status-check`
both publish to `arn:aws:sns:eu-central-1:030179310793:wusool-prod-infrastructure-alerts`,
and that topic has **zero subscriptions**. If prod n8n dies, no one is told.

(Dev's subscription exists but is stuck `PendingConfirmation` — `raoof@azmora.ai`
never clicked the confirm link, so dev alerts don't deliver either.)

## Defect 3 — nothing in this account is backed up

Verified live:

| Check | Result |
|---|---|
| n8n data location | Docker volume `n8n_n8n_data` (compose project prefix) → **the root EBS volume**; no separate data disk exists |
| Prod n8n root volume `vol-0943ab2f832103df1` | `DeleteOnTermination: **True**` |
| EBS snapshots in the account | **zero** |
| AWS Backup plans | **zero** |
| DLM lifecycle policies | **zero** |

**If the prod n8n instance is ever replaced, every workflow, credential, and
execution record is permanently lost.** The only thing preventing that today is
`lifecycle { ignore_changes = [ami] }` at `modules/n8n-ec2/main.tf:164-166` —
the AMI is looked up with `most_recent = true`, so without that block a new
Amazon Linux release forces instance replacement on the next apply.

**Never remove that lifecycle block**, and carry it into the new stacks verbatim.
Phase H replaces it with something that isn't a silent tripwire.

## Defect 4 — the encryption key was not recoverable *(RESOLVED 2026-08-15)*

`N8N_ENCRYPTION_KEY` was never set explicitly. n8n auto-generated it on first
boot into `~/.n8n/config`, inside the `n8n_n8n_data` Docker volume on the root
disk. **Every stored n8n credential — API keys, OAuth tokens, workflow
passwords — is encrypted with it.** Losing the volume would have made those
credentials unrecoverable *even from a perfect database backup*.

**Already done**, extracted from the live instances and verified byte-for-byte:

| Secret | Verified |
|---|---|
| `/wusool/prod/n8n-encryption-key` | matches live prod instance (32 chars) |
| `/wusool/dev/n8n-encryption-key` | matches live dev instance (32 chars) |

Both are **new** secrets; no existing secret was modified.

*Note: the key transited SSM command output, retained by AWS for 30 days. The
instance role holds only `GetSecretValue`, so it could not write the secret
itself. Consider whether to purge that command history.*

**Remaining code change (not yet applied — do it in Step 1):** wire the key in
explicitly so it is no longer generated-and-forgotten. The existing bootstrap
already injects anything under the secret's `env` object as an environment
variable:

```bash
echo "$N8N_SECRET_JSON" | jq -r '.env // {} | to_entries[] | "\(.key)=\(.value)"' >> /opt/n8n/n8n.env
```

So either add `N8N_ENCRYPTION_KEY` under `env` in `/wusool/<env>/n8n` (**no code
change at all**), or have `user_data.sh.tpl` read the new dedicated secret. The
value must be **identical** to what is stored above — a different key silently
breaks every existing credential.

## Defect 5 — security findings route nowhere

GuardDuty and Security Hub are **already enabled** (`dev/main.tf:180-184`, dev's
root only) and are producing real signal. Nothing consumes it:

```
aws events list-rules  ->  []      # zero EventBridge rules
```

No routing to SNS, email or Slack. Combined with Defect 2 (alert topic has no
subscribers), the entire detection stack reports into a void.

**Proof it matters:** a severity **8.0** `Impact:IAMUser/AnomalousBehavior`
finding (421 occurrences) fired on 2026-08-11 and was still `Archived: false`
four days later. It was benign — `sinan.shamsudheen` calling `ssm:SendCommand`
from a previously-unseen ISP (BSNL, India), i.e. GuardDuty correctly spotting a
novel network. **A genuine compromise would have produced identical silence.**

Unreviewed as of 2026-08-15:

| Finding | Detail |
|---|---|
| `Policy:IAMUser/RootCredentialUsage` | 31 occurrences, June. Root credentials used — confirm this was account setup |
| **CRITICAL** — AWS Config not enabled | Compounding: many Security Hub checks *depend* on Config, so **both standards report `INCOMPLETE`** and the compliance picture is partial |
| 14 × LOW (CIS) | No CloudWatch metric filters/alarms for root usage, IAM policy changes, SG changes, unauthorized API calls, console sign-in without MFA, etc. |

**Fix, in order of value:**

1. **Route findings** — an EventBridge rule on GuardDuty findings (severity ≥ 4)
   and Security Hub imported findings, targeting the existing
   `wusool-<env>-infrastructure-alerts` SNS topic. Small, and it converts all
   existing tooling from decorative to functional. Belongs in `stacks/account`
   alongside the detectors. **Do this with Defect 2's subscription fix** —
   neither works without the other.
2. **Enable AWS Config** — resolves the CRITICAL and unblocks full Security Hub
   evaluation. Expect *more* findings afterwards; that is the point.
3. **Then triage the CIS metric-filter set** as a batch, once you can actually
   see the full list.

**Cost note:** GuardDuty bills per GB analyzed, and S3 data events + EBS malware
protection are the expensive features — both are ENABLED. Enabling AWS Config
adds per-configuration-item charges. Worth pulling actual figures from Cost
Explorer before assuming it is negligible.

## Defect 6 — none of this plan's guardrails can currently be enforced

Verified via the GitHub API on 2026-08-15:

| Check | Result |
|---|---|
| Org plan | **`free`**, 8 seats, repository **private** |
| Rulesets API | **`403 — Upgrade to GitHub Pro`** |
| Branch protection on `dev` / `main` | **none configured** (and unavailable on free + private) |
| Merge methods allowed | **squash, merge commit, and rebase all enabled** |
| Current user's repo role | `admin: false`, `push: true` |

Branch protection and rulesets require GitHub **Team** or higher for *private*
repositories. On the current plan that means:

- **"Plan-on-PR as a required status check" cannot be required.** This was the
  guardrail kept after the prod approval gate was declined — it is presently
  advisory only.
- **Direct pushes to `prod` cannot be blocked.** Anyone with write access can
  commit straight to production's branch.
- **Merge method cannot be restricted per branch.** Nothing stops a squash-merge
  into `prod`, which breaks `HEAD^2` and therefore digest resolution (Phase F).
- Required reviewers and GitHub Environments protection rules are likewise
  unavailable, so the declined prod gate could not be turned on even if wanted.
- Whoever executes this plan needs **repo admin**, which the current user does
  not hold.

### What a mistaken squash-merge into `prod` actually does

The Phase F ECR guardrail is **partial** — it covers application code, not
infrastructure:

| Change type | Outcome |
|---|---|
| **App code** | No ECR image exists for the new squashed SHA → digest resolution fails → **deploy fails, prod untouched.** Fails safe. |
| **Infra only** | No digest is needed → **`tofu apply` runs and succeeds.** `prod` silently stops being a superset of `dev`; the next `dev → prod` merge conflicts or double-applies. |

### Mitigations, in order

1. **Recommended: upgrade to GitHub Team** — ~$4/user/month, ≈$32/month at 8
   seats. Unlocks branch protection, required status checks, per-branch
   merge-method restriction via rulesets, and Environments with required
   reviewers (which would also restore the prod approval gate). For a live
   financial-services system currently enforcing **nothing**, this is the
   cheapest risk reduction available in this document. Needs whoever holds repo
   admin.
2. **Until then, detect what you cannot block.** Add
   `.github/workflows/guard-prod-history.yml`, which runs fine on the free plan:

   ```yaml
   on: { push: { branches: [prod] } }
   # ...
   - run: |
       git rev-parse HEAD^2 >/dev/null 2>&1 || {
         echo "::error::Squash or direct commit on prod — HEAD^2 missing. prod must
         receive merge commits only (see Phase C0/F)."; exit 1; }
       git merge-base --is-ancestor origin/dev HEAD || \
         echo "::warning::prod is no longer a superset of dev — back-merge required"
   ```

   It cannot prevent the merge, but it converts a silent divergence into a
   failed run. **This is only useful once notifications are wired — see
   Defect 5.**
3. **Recovery when it happens.** First establish what Terraform already applied;
   an infra-only squash will have deployed. Then: if nobody has pulled, reset
   `prod` and redo the merge as a merge commit. If others have pulled,
   `git revert -m 1` the squash commit and re-merge properly. Either way,
   back-merge `prod → dev` afterwards.

## Step 0 — snapshot, then announce a freeze

**Snapshot first. This is the cheapest insurance in this entire document** — it
converts every subsequent mistake from unrecoverable to recoverable.

```bash
export AWS_PROFILE=wusool AWS_REGION=eu-central-1

# resolve both root volumes (prod is known; dev must be looked up)
PROD_VOL=vol-0943ab2f832103df1
DEV_VOL=$(aws ec2 describe-instances --instance-ids i-02ed4b390b677518b \
  --query 'Reservations[].Instances[].BlockDeviceMappings[].Ebs.VolumeId' --output text)
echo "prod=$PROD_VOL dev=$DEV_VOL"

# snapshot BOTH
PROD_SNAP=$(aws ec2 create-snapshot --volume-id "$PROD_VOL" \
  --description "pre-restructure prod n8n $(date +%F)" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=wusool-prod-n8n-pre-restructure}]' \
  --query SnapshotId --output text)
DEV_SNAP=$(aws ec2 create-snapshot --volume-id "$DEV_VOL" \
  --description "pre-restructure dev n8n $(date +%F)" \
  --tag-specifications 'ResourceType=snapshot,Tags=[{Key=Name,Value=wusool-dev-n8n-pre-restructure}]' \
  --query SnapshotId --output text)

# block until BOTH are usable
aws ec2 wait snapshot-completed --snapshot-ids "$PROD_SNAP" "$DEV_SNAP"
echo "RECORD THESE: prod=$PROD_SNAP dev=$DEV_SNAP"
```

**Write both snapshot IDs into the change ticket.** A snapshot you cannot find
later is not a backup. Do not proceed until `wait snapshot-completed` returns.

Then announce the freeze:

> Do not run `aws ssm send-command` against the prod n8n bootstrap document, and
> do not re-run its SSM association, until further notice. It will take
> production offline.

Say it explicitly in the team channel. People reach for it as the standard fix.

**Follow-up, not blocking:** set up a recurring backup (AWS Backup plan or a DLM
policy on both instances) so this stops being a manual step. Track it as work in
its own right — a production system with no backups is a larger risk than
anything else in this plan.

## Step 1 — fix the Caddyfile template first

`terraform/modules/n8n-ec2/user_data.sh.tpl` generates a **single-hostname**
Caddyfile. That was the root cause of one of the three prior incidents.
Generalize it to a list of hostnames **before** re-registering, or you re-arm a
variant of the same bug.

While in this file, also fix (all confirmed present in the live decoded document):
- `docker-compose-linux-x86_64` hardcoded while `ami_architecture` accepts `arm64`.
- Unpinned images: `docker.n8n.io/n8nio/n8n`, `n8nio/runners:latest`, `caddy:2`.
  A container restart can silently upgrade n8n in production.

Also fix the double render: `modules/n8n-ec2/main.tf:151-157` and `195-201` call
`templatefile()` twice with the same inputs — collapse to one `local`, as
`matching-engine-ec2` already does.

**And wire in `N8N_ENCRYPTION_KEY`** (see Defect 4). Simplest route with no
template change: add it under the `env` object of `/wusool/<env>/n8n`, which the
bootstrap already expands into environment variables. It **must** equal the value
in `/wusool/<env>/n8n-encryption-key` — a different key silently breaks every
stored credential. After the apply, open a credential in the n8n UI to confirm it
still decrypts.

## Step 2 — create `terraform.tfvars`

`terraform/environments/prod/terraform.tfvars.example` **already contains the
correct values** — every one cross-checked against live state this session
(`instance_type=t3.small`, `root_volume_size=50`, `n8n_timezone=Asia/Dubai`,
`alert_email=raoof@azmora.ai`, and critically
`n8n_webhook_url="https://n8n.wusoolcapital.com/"`, the live domain).

```bash
cd terraform/environments/prod
cp terraform.tfvars.example terraform.tfvars
```

Confirm `n8n_webhook_url` resolves to the live site before proceeding. It is the
one value state cannot corroborate — state holds the *retired* domain.

## Step 3 — back up state

```bash
aws s3 cp s3://wusool-tfstate/wusool/prod/terraform.tfstate \
  ./backup-prod-$(date +%F).tfstate --profile wusool
```

**Note:** applying with `tofu` writes OpenTofu's version stamp into the state —
so this apply *is* the OpenTofu migration for prod, de facto. That was verified
safe (Phase A), but take the backup regardless.

## Step 4 — plan, review, apply

```bash
tofu init
tofu plan -var-file=terraform.tfvars
```

**Expected diff** (measured this session against real prod state):

| Resource | Change | Effect |
|---|---|---|
| `module.n8n.aws_ssm_document.bootstrap` | update in place | re-registers with the live domain — **the fix** |
| `module.n8n.aws_instance.n8n` | update in place, `user_data` hash only | **no replacement, no restart**; `user_data` runs only at boot |
| `aws_sns_topic_subscription.email[0]` | create | restores prod alerting — fixes Defect 2 |

`Plan: 1 to add, 2 to change, 0 to destroy` — and **zero** `forces replacement`.
If your plan shows any destroy or any replacement, **stop** and re-read the diff.

Have a second person review the plan output before applying. This is a live
financial-services production system.

```bash
tofu apply -var-file=terraform.tfvars
```

## Step 5 — verify, then lift the freeze

```bash
# 1. the document no longer references the retired hostname
aws s3 cp s3://wusool-tfstate/wusool/prod/terraform.tfstate - --profile wusool \
  | jq -r '.resources[]|select(.type=="aws_ssm_document")|.instances[].attributes.content' \
  | jq -r '.mainSteps[0].inputs.runCommand[]' | grep -o "echo '[A-Za-z0-9+/=]*'" \
  | sed "s/echo '//;s/'//" | base64 -d | grep -c 'n8n-prod.wusoolcapital.com'
# MUST print 0

# 2. the site still serves HTTPS on the live domain
curl -sSI https://n8n.wusoolcapital.com/ | head -1

# 3. prod alerting has a CONFIRMED subscriber (not merely a listed one)
aws sns list-subscriptions-by-topic --profile wusool --region eu-central-1 \
  --topic-arn arn:aws:sns:eu-central-1:030179310793:wusool-prod-infrastructure-alerts \
  --query 'Subscriptions[?SubscriptionArn==`PendingConfirmation`]' --output text
# MUST print nothing. A PendingConfirmation subscription delivers NOTHING —
# it is exactly dev's current broken state, which listing alone would call a pass.
```

**Click the confirmation link** in the SNS email — otherwise the subscription
sits in `PendingConfirmation` and prod alarms still notify nobody, exactly as
dev's does today. Then do the same for dev's pending subscription.

Once all three checks pass, lift the freeze.

> This closes the *current instance* of the bug. It does not stop recurrence —
> that requires the "re-register the bootstrap document from source on every
> deploy" invariant, which is what Phase E's deploy workflows enforce.

---

## Context

This repo grew organically across five workstreams with no shared deployment
convention. Today there is **no CD at all**: `.github/workflows/terraform-ci.yml`
is the only workflow and it runs `fmt` + `validate -backend=false`. Nothing
deploys. dev and prod are two hand-maintained copies of the same code that have
already drifted, and prod is the *less* capable environment — n8n only, no
database, no application, no GuardDuty, no SecurityHub.

The goal is one dev and one prod environment per service, separate VPCs in one
AWS account, **one set of Terraform code parameterised by environment**, and CD
that deploys only what changed — a foundation that scales as more services are
added to this AI-native automation system.

A live survey of AWS account `030179310793` (this session, `wusool` profile)
produced the ground truth below, including a **live production landmine**
(Phase B) that is armed right now. Treat repo documentation as unverified:
`PROGRESS.md`'s claim that prod is Terraform-orphaned was found **stale and
wrong** — prod is fully Terraform-managed.

Where this plan states a fact, it was read from AWS or produced by a real
`tofu plan`, and says so.

---

## Part 0 — Verified ground truth

Everything here was read from live AWS, not from repo docs.

### Compute and network (`eu-central-1`, the only region with workloads)

| Resource | ID | Notes |
|---|---|---|
| `wusool-dev-n8n` | `i-02ed4b390b677518b` | t3.small, dev VPC |
| `wusool-prod-n8n` | `i-0087f9ecb02462b2e` | t3.small, `10.20.1.96`, prod VPC |
| `wusool-dev-matching-engine` | `i-0fb853edb9f185db9` | t2.micro |
| `wusool-scribe` | `i-01bf509a92ed1dcba` | **c6a.xlarge — largest in account, runs in the DEV VPC, untagged for Environment** |
| `wusool-dev-vpc` | `vpc-0ed8db2cc2b5f2cdc` | `10.10.0.0/16` |
| `wusool-prod-vpc` | `vpc-00fd39371dfaae3bf` | `10.20.0.0/16` |
| `wusool-dev-postgres` | — | pg 16.13, db.t4g.micro. **Prod has no database.** |

### State (`s3://wusool-tfstate`, bucket region `me-central-1` — intentional)

| Key | Serial | Written by |
|---|---|---|
| `wusool/dev/terraform.tfstate` | 34 | **Terraform 1.15.6** |
| `wusool/prod/terraform.tfstate` | 13 | **Terraform 1.15.6** |
| `wusool/dev/scribe/terraform.tfstate` | 15 | 1.10.6 (tool ambiguous) |

### Account-level

- GuardDuty: **one** detector, `48d9c79b1f49414bb4e3cddce57c5a11` (`eu-central-1`).
- SecurityHub: **one** hub, subscribed `2026-06-21`, `AutoEnableControls: true`.
- Both created by dev's root — they are account+region singletons.
- **No ECR repositories exist.** **No IAM OIDC provider exists.**
- Secrets: `/wusool/dev/n8n`, `/wusool/prod/n8n`, `/wusool/dev/matching-engine`,
  `/wusool-scribe`, plus the RDS-managed master secret.
  **`/wusool/prod/matching-engine` does not exist.**
- `sg-0684b8cf83abfd065` (hardcoded at `dev/main.tf:93`) = `wusool-scribe-instance`.
- Orphans: `wusool-tfstate-locks` DynamoDB table (`me-central-1`, no backend
  references it); empty VPCs `n8n-dev-vpc` + `n8n-prod-vpc` in `me-central-1`
  (both `10.0.0.0/16`, zero instances/NAT/EIPs, in no state file).
- **No backups of any kind**: zero EBS snapshots, zero AWS Backup plans, zero
  DLM policies. n8n data lives on the root volume with
  `DeleteOnTermination: True`, so instance replacement = permanent data loss.
- Prod SNS alert topic `wusool-prod-infrastructure-alerts` has **zero
  subscriptions** while two CloudWatch alarms publish to it. Dev's subscription
  is stuck `PendingConfirmation`.

### Decisions locked with the user

| Area | Decision |
|---|---|
| Branching | `dev` + `prod`. Merge to `dev` → dev; merge to `prod` → prod. |
| Deploy scope | One workflow; change detection feeds a per-service matrix. |
| Env config | One env-agnostic stack per service; `envs/{dev,prod}.tfvars` committed. |
| State | One state per service per environment. |
| Artifacts | ECR build-once/deploy-by-digest, landed **with** matching-engine's prod stack. |
| Migrations | Alembic, SQLAlchemy models as source of truth for all ~22 tables. |
| Guardrails in | Plan-on-PR as required check; auto back-merge PR after prod deploy. |
| Guardrails out | No prod approval gate; no dev-ancestry check. See *Accepted risks*. |
| Toolchain | **OpenTofu** (verified non-breaking against real prod state). |
| DB ingress | Consumers attach themselves to Postgres; Postgres owns no allow-list. |
| Config vs secrets | Config in committed tfvars; only true secrets in Secrets Manager; OIDC for CI auth. |

---

## Part 1 — Execution

Phases A and B are blocking and must complete in order. C onward can overlap.

---

### Phase A — Standardize on OpenTofu

**Decision: OpenTofu.** Verified safe by direct test, not inference.

#### The situation

State was written by **HashiCorp Terraform 1.15.6** (OpenTofu's releases top
out at `v1.12.5`, so `1.15.6` cannot be OpenTofu; both `.terraform.lock.hcl`
files declare `registry.terraform.io/hashicorp/aws` under the header
`maintained automatically by "terraform init"`, with zero
`registry.opentofu.org` references). The only binary installed is
**OpenTofu 1.12.5**. CI pins `1.9.8` via `hashicorp/setup-terraform` and
survives only because it runs `init -backend=false` and never opens the state.

#### Verified: the migration does not break anything

OpenTofu 1.12.5 was run against a **copy of the real prod state** (34 resources,
stamped `1.15.6`) using a local backend, so the S3 state was never touched:

```
Plan: 1 to add, 2 to change, 0 to destroy
"forces replacement" occurrences: 0
```

- **OpenTofu reads Terraform-1.15.6 state without complaint.** It does not apply
  Terraform's "state written by a newer version" gate to a foreign lineage.
  (An earlier draft of this plan claimed nobody could plan against dev/prod —
  that was wrong and is corrected here.)
- **No instance is replaced or restarted.** The only `aws_instance` change is
  the `user_data` hash. `user_data_replace_on_change` is unset (defaults
  `false`), so it is an in-place attribute update; `user_data` executes only at
  boot. Prod n8n keeps running throughout.
- **The 2 changes are exactly the Phase B corrective work** — the stale
  `aws_ssm_document.bootstrap` and its matching `user_data`. The `1 to add` was
  an SNS email subscription, an artifact of the placeholder `alert_email` used
  in the test; confirm against the real tfvars.

`CD_Restructure.md:18,286` claims live verification via `tofu` commands. Those
are now plausible after all — but that file has already been proven wrong
elsewhere, so continue to treat its claims as unverified.

**Steps**

1. Pin OpenTofu **1.12.5** (current release). Rename
   `terraform/.terraform-version` → `terraform/.opentofu-version`.
2. Set `required_version` in every root/stack to `>= 1.12.0`.
3. Swap CI from `hashicorp/setup-terraform` to **`opentofu/setup-opentofu`**,
   reading the version file. Update the required status-check names in branch
   protection to match the renamed jobs (`CONTRIBUTING.md` lists them).
4. Install `tofu` on every workstation; remove any `terraform` binary to prevent
   accidental mixed use. Verify `tofu version` matches the pin.
5. **Regenerate every `.terraform.lock.hcl`** — `tofu init -upgrade`, then
   commit. Same provider (`hashicorp/aws 5.100.0`), different registry path
   (`registry.opentofu.org`).
6. **Back up state before the first real apply**:
   `aws s3 cp s3://wusool-tfstate/wusool/<env>/terraform.tfstate ./backup-<env>-<date>.tfstate`
   for dev and prod. The bucket is versioned, but take the explicit copy anyway
   — in practice this migration is one-way.
7. Update `CONTRIBUTING.md`: tool, version, install command, and `tofu` in all
   example commands.

**Acceptance:** `tofu init && tofu plan` against the real backends for dev and
prod both succeed. Prod shows **0 to destroy** and **no "forces replacement"**.
Record prod's plan output — it is the input to Phase B.

---

### Phase B — Defuse the live production landmine

**See the "🔴 STOP — DO THIS FIRST" runbook at the top of this file.** It is the
single source of truth for this work: the two defects, the freeze notice, the
template fixes, the expected diff, and the verification commands.

Summary for sequencing purposes only: the registered prod SSM bootstrap document
hardcodes a hostname retired in August, and prod's alarm topic has no
subscribers. One targeted apply against the existing
`terraform/environments/prod` root fixes both. It has **no prerequisites** and
should be done before any restructuring begins.

Recurrence prevention is Phase E's job, not this one — the invariant is that the
bootstrap document must be re-registered from current source as part of every
deploy, and "re-run the existing document" must never be the only available
path. This applies to `matching-engine-ec2` too, which has the identical
structure.

### Phase C0 — Merge strategy and what it implies

**Agreed model:**

| Transition | Merge type | Effect on history |
|---|---|---|
| `feature/*` → `dev` | **squash** | feature commits collapse to one new SHA on `dev` |
| `dev` → `prod` | **normal merge** (merge commit) | dev's commits are **preserved** in prod's history; prod becomes a **superset** of dev |

Three consequences that shape the rest of this plan:

**1. It confirms "build on `dev` only" (Phase F).** A normal merge still creates a
**merge commit with a new SHA**, so `github.sha` on the prod branch is *not* the
SHA that was built and tested on `dev` — even when the resulting tree is
byte-identical. Rebuilding there would produce a different image tag for
identical source, and resolve different base-image layers besides. Build once on
`dev`; the prod branch only ever *deploys* an already-tested digest.

**2. One merge deploys an environment end to end.** Because the merge preserves
dev's commits, the prod-branch workflow can *resolve* which already-built image
to deploy rather than rebuilding: the promoted commit is the merge commit's
second parent (`HEAD^2`), which is dev's tip and is already in ECR.

```
feature/*  --squash-->  dev  --> builds image, tofu apply, rolls app  (1 merge)
dev  --normal merge--> prod  --> resolves that same digest from ECR,
                                 tofu apply, rolls app                (1 merge)
```

Prod runs the **byte-identical artifact** dev ran, with no bot PR and no second
merge. This works *because* the merge is a normal one — a squash would destroy
`HEAD^2` and the digest could not be resolved. See Phase F.

**3. `backmerge.yml` becomes a safety net rather than routine.** Since prod is a
superset of `dev` by construction, the only way they diverge is a **Path B
hotfix** (branched from `prod`, merged into `prod`; see Phase F). Keep the workflow
for exactly that case — it is the known weakness of this branching model — but
expect it to fire rarely.

*Bonus:* because the merge preserves dev's SHAs, `git merge-base --is-ancestor
$SHA origin/dev` would work reliably if you ever want the dev-ancestry check
that was declined (see *Accepted risks*). Squash-merging `dev` → prod would
break that property, which is a further reason to keep it a normal merge.

#### C0a. Creating `prod`, and what to do with `main`

**Branch `prod` from `dev` — not from `main`.** Verified:

| Branch | Top-level layout |
|---|---|
| `dev` | `.agents .claude .github **database** scripts terraform **workflows**` |
| `main` | `.agents .claude .github **DOCS** scripts terraform` |

`main` is **structurally obsolete** — it predates the `database/` and
`workflows/` restructure. `dev` is 50 commits ahead; `main` is 2 ahead (a stale
"sync main with dev" attempt, #12). Merge base is `5441211`, and a `dev → main`
merge produces **11 conflicts**.

Branching prod off `main` would give the production branch a repo layout that no
longer exists, and make the first promotion an 11-conflict merge.

**The "50 untested commits become production-bound" objection does not apply
here**, because **no CD exists yet** — nothing fires on `prod`. Production's
actual definition is its Terraform state plus `terraform/environments/prod`
(n8n-only), not which branches exist. Creating `prod` changes nothing running.
By the time Phase E wires deploys, prod's stacks are explicit and reviewed.

```bash
git fetch origin
git push origin origin/dev:refs/heads/prod     # create prod at dev's tip
gh repo edit --default-branch dev             # make dev the default
```

**Then retire `main`.** Once `prod` exists and `dev` is default, `main` is
orphaned and actively misleading — someone will branch from it. Tag it first so
nothing is lost:

```bash
git tag archive/main-pre-restructure origin/main
git push origin archive/main-pre-restructure
git push origin --delete main
```

Its 2 unique commits are stale doc/layout changes that `dev` has since
superseded; confirm nothing is uniquely needed before deleting.

---

### Phase C — Branch and repo hygiene

No risk, no dependencies. Can run in parallel with A/B.

1. **Make `dev` the GitHub default branch** (currently `main`, per
   `git symbolic-ref refs/remotes/origin/HEAD`). `CONTRIBUTING.md` already
   mandates PRs into `dev`.
2. **Create the `prod` branch from `dev`** (see C0a below), then set branch
   protection on both `dev` and `prod`: require PR, require the plan-on-PR check
   (Phase E), block direct pushes, and restrict `prod` to merge commits. The
   check must be required on **`prod` too**, not just `dev` — see Phase E for why
   that is load-bearing.

   **Blocked on Defect 6.** Branch protection and rulesets are unavailable on
   the current free/private plan, and the intended operator is not repo admin.
   Until the plan is upgraded, none of this step is enforceable — ship
   `guard-prod-history.yml` as detection and treat the rest as convention.
3. Add `.github/CODEOWNERS`. `CONTRIBUTING.md:121-122` already instructs
   enabling "Require review from Code Owners" and the file does not exist.
4. Fix `CONTRIBUTING.md:17` — names `github.com/Azmora-ai/wusool-infra.git`;
   actual remote is `github.com/wusool-capital/wusool-infra.git`.
5. Fix `terraform/environments/dev/variables.tf:169-173` —
   `matching_engine_git_ref` defaults to `"main"`, so dev's EC2 clones prod's
   branch. Set to `dev`. (Phase F deletes this variable entirely.)
6. Fix `README.md`'s stale "matching-engine is a placeholder" claim.
7. Delete the empty `me-central-1` VPCs `n8n-dev-vpc` / `n8n-prod-vpc` after
   team confirmation. (The unused `wusool-tfstate-locks` table and
   `terraform/bootstrap/` itself are handled in **D0a** — they need the state
   bucket adopted into `stacks/account` first, so they are not standalone
   hygiene.)

---

### Phase D — Terraform restructure

Replaces the two hand-maintained env roots with **one env-agnostic stack per
service**. This is what kills the "two different folders for n8n dev and prod"
problem.

#### D0a. What happens to `terraform/bootstrap/`

**Purpose:** it solves the chicken-and-egg problem — every other root keeps its
state in `s3://wusool-tfstate`, but something must create that bucket first, and
that something cannot itself store state there. So `bootstrap/` deliberately has
**no `backend` block** (local state) and is run **once, by hand, at project
birth**, creating the state bucket (+ versioning, AES256, public-access block)
and a DynamoDB lock table.

**Verified live:** the bucket configuration matches `bootstrap/main.tf` exactly —
versioning `Enabled`, `AES256`, all four public-access blocks `True`. Bucket
versioning is therefore a genuine recovery path for a bad `state push`.

**Two problems:**

1. **Its state is lost.** Not in S3 (only `dev`, `prod`, `dev/scribe` keys
   exist), and no local `terraform.tfstate` in the repo — correctly gitignored,
   which means it survives only on whoever ran it in June, or nowhere. The
   bucket holding *all* your state is currently unmanaged and undriftable.
   Running `tofu apply` there today would attempt to **create**
   `wusool-tfstate` and fail with `BucketAlreadyExists`.
2. **The DynamoDB table was dead weight — now deleted.** Both backends use
   `use_lockfile = true` (S3-native locking), so nothing referenced
   `wusool-tfstate-locks`. Verified before removal: zero references in dev, prod
   *or scribe* state, and its single item was a stale **digest** record
   (`wusool-tfstate/wusool/dev/terraform.tfstate-md5`, no `Info` attribute, so
   not an active lock) left over from before the switch. **Deleted 2026-08-15**;
   `me-central-1` now has no DynamoDB tables and state remains readable.

**Action:**

- **Adopt the bucket into `stacks/account`** via `tofu import`, so it becomes
  managed and drift-detected again. The self-reference (a bucket managing
  itself) is fine — it already exists, so Terraform simply adopts it.

  **Import all four resources, not just the bucket.** `bootstrap/main.tf`
  declares them separately, and importing only `aws_s3_bucket` leaves the other
  three unmanaged, so the plan will *not* come back clean:

  ```bash
  tofu import aws_s3_bucket.tfstate                                wusool-tfstate
  tofu import aws_s3_bucket_versioning.tfstate                     wusool-tfstate
  tofu import aws_s3_bucket_server_side_encryption_configuration.tfstate wusool-tfstate
  tofu import aws_s3_bucket_public_access_block.tfstate            wusool-tfstate
  ```

  Then confirm `plan` reports `0 to add, 0 to change, 0 to destroy`. Live config
  was verified to match the code (versioning `Enabled`, `AES256`, all four public
  -access blocks `True`), so a clean plan is achievable — but only once all four
  are imported.
- **Add `lifecycle { prevent_destroy = true }`** to it. Without this, a
  `tofu destroy` on `stacks/account` would try to delete the bucket holding its
  own state, and every other stack's state with it.
- **Delete `aws_dynamodb_table.tfstate_locks` and its output from the code.**
  *(The live table is already gone — deleted 2026-08-15.)*
- **Delete `terraform/bootstrap/`**, moving the "how to recreate the backend from
  nothing" instructions into a short README rather than leaving dead HCL that
  cannot be applied.

#### D0. What happens to `terraform/environments/` — and to the running instances

**The `environments/dev` and `environments/prod` directories are deleted.**
Today they are two hand-maintained copies of the same code that have already
drifted (`prod/variables.tf:59-62` has an `ami_architecture` validation block
that `dev/variables.tf:74-78` lacks). Replacing them with one parameterised
stack set is the whole point of this phase.

```
BEFORE                                   AFTER
terraform/                                terraform/
  environments/                             stacks/
    dev/                                      account/     ← one state, no tfvars
      backend.tf   key: wusool/dev            base/        ← VPC, CloudTrail, SNS
      main.tf      network + n8n +            n8n/
                   bedrock×2 +                postgres/
                   matching-engine +          matching-engine/
                   postgres  (one state)    envs/
      variables.tf / providers.tf             dev.tfvars
    prod/                                     prod.tfvars
      backend.tf   key: wusool/prod
      main.tf      network + n8n only
      variables.tf / providers.tf   ← a drifted hand-copy
```

`dev` vs `prod` stops being a *directory* and becomes a backend key plus a
`-var-file`.

**Do the live instances get destroyed, or lose data? No.**

`tofu state mv` is **bookkeeping only** — it rewrites which state file records a
resource and makes **zero AWS API calls** to create, modify, or destroy
anything. `i-0087f9ecb02462b2e` (prod) and `i-02ed4b390b677518b` (dev) keep
running throughout and never observe the change. That is exactly what the
`0 to add, 0 to change, 0 to destroy` gate after every move proves.

**Three ways this could still go wrong — all avoidable, all worth naming:**

1. **Dropping `lifecycle { ignore_changes = [ami] }`** when writing the new
   stacks. The AMI data source uses `most_recent = true`, so without that block
   a newer Amazon Linux release **forces instance replacement** — and since n8n's
   data lives on the root volume with `DeleteOnTermination: True` and **no
   snapshots or backup plans exist**, that is total, permanent data loss.
   **This is the single most dangerous mistake available in this phase.**
   Copy the lifecycle block verbatim and diff it before applying.
2. **Applying an old `environments/` root after its resources have been moved
   out.** Its state is now empty, so Terraform would happily build a **second
   parallel production stack**. Delete those directories the moment migration is
   green — do not leave them lying around "just in case".
3. **EIP handling.** Moving state does not release an EIP, but a mishandled
   `aws_eip_association` can change the public IP and break DNS. Verify the EIP
   and its association move together, and confirm the address afterwards.

**Prerequisite:** the EBS snapshots from Step 0 of the top-of-file runbook must
exist and read `State: completed` before any `state mv` is run.

#### D0b. Prerequisite: `.gitignore` currently blocks the committed tfvars

The whole design depends on `terraform/envs/{dev,prod}.tfvars` being **in git**.
They currently would not be — `.gitignore:23` ignores `*.tfvars` and only
`!*.tfvars.example` is re-included. Verified: `git check-ignore -v
terraform/envs/dev.tfvars` matches `.gitignore:23`. Committing them would fail
**silently** — `git add` skips them without error, and the first CI run fails on
a missing var-file.

Add a narrow un-ignore *before* creating the files, keeping the broad rule so a
stray `terraform.tfvars` in a stack directory stays ignored:

```gitignore
*.tfvars
*.auto.tfvars
*.tfvars.json
!*.tfvars.example
!terraform/envs/*.tfvars      # non-secret per-env config, deliberately committed
```

Verify with `git check-ignore -v terraform/envs/dev.tfvars` returning nothing.

Only non-secret config goes here (region, CIDRs, instance type, domains,
timezone, image digest). Secrets stay in Secrets Manager — see D2a.

#### D1. Target layout

```
terraform/
  # bootstrap/ DELETED — state bucket adopted into stacks/account (see D0a)
  modules/                       # unchanged names
    network/  n8n-ec2/  matching-engine-ec2/  postgres-rds/  bedrock-access/
  stacks/
    account/                     # applied ONCE — not per-env
                                 #   GuardDuty, SecurityHub, OIDC provider+roles,
                                 #   and the wusool-tfstate bucket (prevent_destroy)
    base/                        # per-env: VPC, CloudTrail, SNS
    n8n/
    postgres/
    matching-engine/
  envs/
    dev.tfvars
    prod.tfvars
```

#### D2. Why three tiers, not two

dev and prod share one account and one region. `aws_guardduty_detector` is
one-per-account-per-region; `aws_securityhub_account` is per-account. **Verified
live: exactly one of each exists**, created by dev's root
(`dev/main.tf:180-184`). Putting them in a per-env stack means applying
`stacks/base` with `envs/prod.tfvars` **fails on both resources**.

- `stacks/account/` — single state `wusool/account/terraform.tfstate`, **no
  `-var-file`**. Owns GuardDuty, SecurityHub, the GitHub OIDC provider and its
  IAM roles (Phase E).
- `stacks/base/` — per-env. Owns `module "network"`, the CloudTrail stack, and
  `aws_sns_topic.alerts` + subscription. CloudTrail stays per-env because bucket
  and trail names are already `${project}-${environment}-…` in both roots
  (`dev/main.tf:132,172`, `prod/main.tf:52,112`), so they do not collide.

##### Dev and prod stay in fully separate VPCs

This is **already true today and is preserved by the restructure** — verified
live:

| VPC | ID | CIDR | Contains |
|---|---|---|---|
| `wusool-dev-vpc` | `vpc-0ed8db2cc2b5f2cdc` | `10.10.0.0/16` | dev n8n, dev matching-engine, scribe |
| `wusool-prod-vpc` | `vpc-00fd39371dfaae3bf` | `10.20.0.0/16` | prod n8n |

Non-overlapping CIDRs, **no peering, no transit gateway** — the two
environments cannot reach each other over the network.

`stacks/base` is applied **once per environment**, each with its own backend key
and its own `-var-file`, so each environment creates and owns its own VPC,
subnets, IGW and route tables. CIDRs come from `envs/dev.tfvars` /
`envs/prod.tfvars`. One copy of the code, two completely independent networks —
that is the whole point of the parameterised-stack design.

Note that **scribe currently has no prod presence** — it runs only in the dev
VPC. Standing up scribe prod (Part 2) places it in `wusool-prod-vpc` by reading
`stacks/base` prod's outputs, with no code duplication.

**Move GuardDuty/SecurityHub with `state mv`, never `state rm` + re-apply.**
Recreating them disables and re-enables SecurityHub, discarding finding history
and per-control config accumulated since 2026-06-21. This is the one
destructive move in Phase D that a `plan` will *not* show as a `destroy`.

#### D2a. Configuration policy — what goes where, and why not everything in Secrets Manager

Centralizing *every* variable in Secrets Manager was considered and **rejected**.
It is appealing (one place to manage) but breaks two things this plan depends on:

- **It disables the only prod guardrail.** The prod approval gate was declined,
  so the plan-on-PR comment is the sole human review production receives. If
  `instance_type`, CIDRs, or domains live in Secrets Manager, changing prod
  config produces **no diff in any PR** — someone edits a secret in the console
  and the next deploy silently changes behavior, reviewed by nobody. No
  `git blame`, no `git revert`, no code review.
- **It is the exact failure being fixed.** Prod's `terraform.tfvars` was never
  in version control, and that is precisely why the drift went unnoticed for
  months.
- **`data "aws_secretsmanager_secret_version"` writes the resolved secret into
  the state file in plaintext.** Reading more through Terraform enlarges the
  blast radius of the S3 state object rather than shrinking it.

The split to enforce:

| Kind | Where | Why |
|---|---|---|
| Config — region, CIDRs, instance type, domains, volume size, timezone | committed `envs/*.tfvars` | reviewable, diffable, revertable; appears in the PR plan |
| Secrets — DB passwords, Slack tokens, API keys | Secrets Manager; **ARN passed to the instance, value fetched at runtime by the instance role** | never enters Terraform state |
| AWS auth for CI | **GitHub OIDC** | no long-lived key exists to leak |

`user_data.sh.tpl` already implements the runtime-fetch pattern correctly (the
instance pulls its own secret via its instance profile). **Preserve it.**

**Do not add a static AWS access key to GitHub Actions.** Long-lived `AKIA…`
keys are the most commonly leaked AWS credential; OIDC issues short-lived
tokens with nothing to rotate or revoke, and is less setup, not more.

##### GitHub's 100-secret limit does not bind this design

A reasonable objection is that GitHub caps repository secrets at 100, so
config there would eventually have to migrate to AWS anyway. **This design
never puts config in GitHub**, so the ceiling is never approached:

| Store | Contents | Count |
|---|---|---|
| GitHub secrets/vars | 3 OIDC role ARNs (`plan`, `apply-dev`, `apply-prod`) — not secret; they may sit in the workflow YAML in plaintext | **0–3 of 100** |
| AWS Secrets Manager | `database_url`, `github_token`, `slack_bot_token`, `slack_signing_secret`, `smtp_*` — **every real secret, already there today**, fetched at runtime by the instance role | all |
| Git (`envs/*.tfvars`) | 45 variables across dev+prod, **zero marked `sensitive`** — region, CIDRs, instance type, volume size, domain, timezone | 45 |

Adding a service adds **one** Secrets Manager entry and **one** tfvars block —
zero GitHub secrets. Thirty more services and the GitHub count is still 3.

The 100-secret ceiling is a real constraint for teams who put per-service
config into **GitHub Environment variables** — a pattern explicitly rejected
here, partly for that reason and mainly because it makes prod config changes
invisible to code review.

**Secrets are therefore already fully centralized in AWS.** The remaining 45
values are not secrets, are not in GitHub, and stay in git precisely so that
changing them is reviewable.

#### D3. How one directory serves both environments

Partial backend — no interpolation needed, and no duplicated directories:

```hcl
# terraform/stacks/<name>/backend.tf
terraform {
  backend "s3" {}
}
```

```bash
tofu -chdir=terraform/stacks/$STACK init -reconfigure \
  -backend-config="bucket=wusool-tfstate" \
  -backend-config="region=me-central-1" \
  -backend-config="key=wusool/$ENV/$STACK/terraform.tfstate" \
  -backend-config="use_lockfile=true" \
  -backend-config="encrypt=true"

tofu -chdir=terraform/stacks/$STACK apply -var-file=../../envs/$ENV.tfvars
```

`dev` vs `prod` is a backend `key` and a `-var-file`. Nothing else.

#### D4. Service stacks

Each reads `stacks/base` via `terraform_remote_state` and instantiates its
module. `stacks/base` outputs: `vpc_id`, `public_subnet_id`, `private_subnet_id`,
`database_private_subnet_ids`, `alarm_topic_arn`.

Bedrock IAM attachment moves into the stack owning the role it attaches to
(`stacks/n8n`, `stacks/matching-engine`) rather than two loose module blocks.

#### D4a. Database access: the consumer declares it, not Postgres

The hardcoded `"sg-0684b8cf83abfd065"` at `dev/main.tf:93` is
`wusool-scribe-instance` — a real cross-service dependency. Two ways to model
it, and the choice decides how much work "add scribe prod" is:

**Option A — allow-list in Postgres (one line per consumer per env).**
`stacks/postgres` keeps the list; `envs/prod.tfvars` gets scribe-prod's SG ID.
The whole allow-list is visible in one file. But adding any service means:
create it → copy its SG ID → paste into wusool-infra → apply. A manual,
ordered, cross-repo step every time.

**Option B — consumers attach themselves (recommended).**
`stacks/postgres` exports `security_group_id` and owns **no** allow-list. Each
consumer reads it from remote state and creates its own ingress rule:

```hcl
resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = data.terraform_remote_state.postgres.outputs.security_group_id
  referenced_security_group_id = aws_security_group.scribe.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
}
```

Adding scribe prod then requires **zero changes in wusool-infra** — apply
scribe's stack with `prod.tfvars` and it wires itself. This is what scales as
services are added.

**Required change if choosing B:** `modules/postgres-rds/main.tf:1-16` builds
its SG with an inline `dynamic "ingress"` block. **Inline `ingress` blocks and
standalone `aws_vpc_security_group_ingress_rule` resources cannot coexist on
the same security group** — each removes the other's rules on apply. The module
must be converted to standalone rule resources first, in the same change.

Trade-off to accept with B: the complete allow-list is no longer readable from
one file. Mitigate by tagging every rule with its consumer and documenting the
convention in `stacks/postgres/README.md`.

`stacks/postgres` must export `security_group_id` under either option.

Ordering is enforced by the workflow, not Terraform: `account` → `base` →
services. Cross-stack reads are one-directional.

#### D5. State migration — dev first, prod only after dev is green

Per stack, per environment:

```bash
SRC=terraform/environments/dev
DST=terraform/stacks/n8n

# 0. record the version ID first, so a bad push is recoverable
aws s3api list-object-versions --bucket wusool-tfstate \
  --prefix wusool/dev/terraform.tfstate --max-items 1 \
  --query 'Versions[0].VersionId' --output text

# 1. pull the source state
tofu -chdir=$SRC state pull > /tmp/old.tfstate
cp /tmp/old.tfstate /tmp/old.tfstate.bak      # keep an untouched copy

# 2. move the module OUT of the source copy and INTO a new file
tofu state mv -state=/tmp/old.tfstate -state-out=/tmp/n8n.tfstate \
  module.n8n module.n8n

# 3. push the RECEIVING state
tofu -chdir=$DST init -reconfigure -backend-config=...   # see D3
tofu -chdir=$DST state push /tmp/n8n.tfstate

# 4. *** PUSH THE MODIFIED SOURCE STATE BACK *** — without this the old root
#     still owns module.n8n and TWO states manage the same live resources
tofu -chdir=$SRC state push /tmp/old.tfstate

# 5. verify BOTH sides
tofu -chdir=$SRC  state list | grep -c '^module\.n8n\.'   # MUST be 0
tofu -chdir=$DST  state list | grep -c '^module\.n8n\.'   # MUST be > 0
tofu -chdir=$DST  plan -var-file=../../envs/dev.tfvars     # MUST be 0/0/0
tofu -chdir=$SRC  plan -var-file=terraform.tfvars          # MUST NOT propose
                                                           # recreating n8n
```

**Step 4 is the one that is easy to skip and expensive to miss.**
`tofu state mv -state=X -state-out=Y` removes the resource from the *local copy*
X — it does not write X back to the remote backend. Skip the push and the source
state still owns `module.n8n`, so two states manage the same live resources:
applies from either root fight each other, and a `destroy` in either one tears
down resources the other still tracks. Note this is *not* a duplicate-stack
scenario (the resources remain in the old state, so nothing gets re-created) —
it is worse, because both roots believe they are the owner.

`state push` acquires the backend lock, so do not run these concurrently with
anyone else's apply — see the coordination note below.

**Rollback:** if step 5 fails, re-push `/tmp/old.tfstate.bak` to the source
backend and remove the destination state object. This is why step 0 records the
version ID.

**Coordinate first — dev is actively being worked on.** Dev state was written
twice on 2026-08-15 at 14:47 UTC (132KB → 136KB → 138KB, the signature of a real
apply), while prod state has been untouched since 2026-07-20. Agree a window with
whoever is applying to dev before starting the migration; a concurrent apply
during a `state mv` is how states get corrupted.

**Acceptance for every single move: `0 to add, 0 to change, 0 to destroy`.**
Anything else — stop and reconcile. Do not apply your way out of a bad move.

**Additionally, before any apply in the new stacks, grep the plan for
`forces replacement` and confirm it returns nothing.** A `~ update in place` on
an instance is safe; a replacement destroys the root volume and, with no
backups, the n8n data with it. See D0.

Record the S3 version-ID of each state object before touching it; the bucket has
versioning enabled, so a bad push is recoverable.

Delete `terraform/environments/` only after both environments are migrated and
green.

---

### Phase E — CI/CD workflows

#### E1. Auth: OIDC, no static keys

In `stacks/account`: `aws_iam_openid_connect_provider` for
`token.actions.githubusercontent.com`, plus three roles with `sub` conditions:

| Role | Trust | Permissions |
|---|---|---|
| `wusool-gha-plan` | any branch / PR | read-only + state read/write (locking) |
| `wusool-gha-apply-dev` | `refs/heads/dev` | apply on dev |
| `wusool-gha-apply-prod` | `refs/heads/prod` | apply on prod |

#### E2. Files

```
.github/workflows/
  ci.yml               # fmt, validate, ruff, ty, pytest, PSScriptAnalyzer — path-filtered
  terraform-plan.yml   # on: pull_request -> plan + PR comment (required check)
  deploy.yml           # on: push to dev|prod -> detect changes -> matrix apply
  _terraform.yml       # reusable: init/plan/apply for (stack, env)
  backmerge.yml        # after successful prod deploy, open prod -> dev PR
```

#### E3. `terraform-plan.yml` must plan against the PR's **base** branch

Load-bearing, because the prod approval gate was declined: **the plan comment on
the `dev -> prod` PR is the only human review production ever gets.**

Wired as a bare `on: pull_request`, every PR plans against `envs/dev.tfvars` —
including the promotion PR, whose comment would show a **dev** diff while
**prod** is what changes. The one chosen guardrail would be silently inert on
the only PR where it matters.

```yaml
env: ${{ github.event.pull_request.base.ref == 'prod' && 'prod' || 'dev' }}
```

#### E4. `deploy.yml`

```yaml
on:
  push:
    branches: [dev, prod]
  workflow_dispatch:
    inputs:
      stack:       { type: choice, options: [account, base, n8n, postgres, matching-engine] }
      environment: { type: choice, options: [dev, prod] }

jobs:
  detect:
    # env = dev if ref==dev else prod
    # dorny/paths-filter maps changed paths -> affected stacks:
    #   terraform/stacks/n8n/**, terraform/modules/n8n-ec2/**  -> n8n
    #   terraform/stacks/base/**, terraform/modules/network/** -> base (+ all downstream)
    #   workflows/wusool-toolkit/matching-engine/**            -> matching-engine (app only)
    # outputs a JSON matrix
  base:
    if: contains(needs.detect.outputs.stacks, 'base')
    uses: ./.github/workflows/_terraform.yml
  services:
    needs: [detect, base]
    strategy:
      matrix: { stack: "${{ fromJson(needs.detect.outputs.stacks) }}" }
      fail-fast: false
    uses: ./.github/workflows/_terraform.yml
```

Three details that are easy to get wrong:

- **Concurrency**: group `deploy-${{ env }}-${{ matrix.stack }}` with
  **`cancel-in-progress: false`**. Cancelling mid-apply orphans state locks.
- **A change under `terraform/modules/**` must fan out to every stack consuming
  that module.** This is the one path-filter mistake that silently skips a
  needed deploy.
- **Change-detection base ref**: do *not* use `github.event.before`. If a deploy
  fails, the next push's `before` skips the failed range and those changes never
  deploy. Write the deployed SHA to SSM
  (`/wusool/<env>/<stack>/deployed_sha`) after each green apply and diff against
  that. First run falls back to deploying everything.

#### E5. `backmerge.yml`

On a successful `deploy.yml` run against `prod`, open a `prod -> dev` PR if
`dev` is behind. This is the chosen mitigation for "hotfix merged to `prod` gets
silently reverted on the next promotion" — the known weakness of the dev/main
model.

#### E6. `ci.yml` — first real coverage for most of this

Path-filtered jobs:
- Terraform `fmt` + `validate`, retargeted at `stacks/*`.
- matching-engine `ruff` / `ty` / `pytest` — already configured in
  `pyproject.toml` but **nothing runs them today**.
- PSScriptAnalyzer over `workflows/**/scripts/**` and `database/*.ps1`.
- From Phase G: `alembic upgrade head` against a throwaway Postgres service
  container, then `alembic check` for un-modelled drift.

---

### Phase F — ECR + matching-engine reaches prod

Landed together deliberately, so prod **never** runs the build-on-box path and
there is no second cutover on a live service later.

Today `user_data.sh.tpl` does `git clone` + `docker compose build` on the
instance. Dev and prod would build *different images* from the same source ref
(the `python:3.12-slim` base layer moves; `uv.lock` pins Python deps but not the
base image). Rollback requires a rebuild, and a build failure happens on the live
box mid-deploy.

**Steps**

1. `aws_ecr_repository` per app — immutable tags, scan-on-push, lifecycle policy
   keeping the last N images. (None exist today.)
2. **One merge = build + apply + roll. Build on `dev`; *resolve* on `prod`.**

   The requirement is that a single merge fully deploys that environment — infra
   *and* application — with no second bot PR. That is achievable without
   rebuilding on `prod`, which would otherwise break the artifact guarantee (a
   normal merge creates a merge commit with a **new SHA**, and a rebuild resolves
   different base layers, so prod would run something dev never tested).

   ```
   merge to dev:
     detect changed services
     for each: build -> push ECR as sha-<dev-tip> -> capture sha256 digest
               tofu apply -var image_digest=<digest>
               roll the app (see below)

   merge dev -> prod:
     detect changed services
     SHA = HEAD^2   (second parent of the merge commit = dev's tip)
           HEAD     (fallback, if the merge fast-forwarded)
     digest = ECR lookup for tag sha-<SHA>        <-- NO BUILD
     tofu apply -var image_digest=<digest>
     roll the app
   ```

   Both are one merge and fully automatic, and prod runs the **byte-identical
   image** dev ran, because it is literally the same image.

   **Partial guardrail — know its limit.** If the ECR lookup returns nothing the
   prod deploy fails loudly, which can only happen when a commit reached `prod`
   with no image built for it. That is a soft dev-ancestry check for **app code
   at no extra cost** — but it does **not** cover infrastructure-only changes,
   which need no digest and will apply successfully even from a squash-merge.
   `guard-prod-history.yml` (Defect 6) covers that gap.

   **Hotfixes still work — three paths, none of which weaken the guardrail.**
   The check only bites when a commit reaches `prod` *without a built image*, so
   the answer is to make sure hotfix commits get built, not to relax it.

   | Path | When | Flow |
   |---|---|---|
   | **A** | `dev` and `prod` are in sync (most hotfixes) | `fix → PR → dev` (auto-deploys, so it is genuinely tested) `→ merge dev→prod`. Two merges, both automatic. |
   | **B** | `dev` holds unreleased work you cannot ship | `git checkout -b hotfix/x prod` → fix → **PR into `prod` as a merge commit**. `build-push.yml` also triggers on `hotfix/**`, so `sha-<hotfix-tip>` is already in ECR; prod resolves `HEAD^2` and finds it. Then back-merge `prod → dev` (`backmerge.yml`). |
   | **C** | Emergency; A and B are both blocked | `workflow_dispatch` on `deploy.yml` with `ref` + `build: true`. Deliberate and logged. |

   So **`build-push.yml` triggers on `dev` and `hotfix/**`** — never on `prod`.

   **Constraint for Path B:** the PR into `prod` must be a **merge commit, not a
   squash**, or `HEAD^2` will not exist and the digest cannot be resolved. Same
   rule as `dev → prod`: squash into `dev`, merge-commit into `prod`. Keep both
   merge methods enabled in repo settings and enforce the split with branch
   rulesets if available.

   #### 🔴 The deploy MUST poll the bootstrap and fail on error

   **Demonstrated live on 2026-08-16, three times.** `tofu apply` reports
   `Apply complete!` as soon as it has *registered* the SSM document. It does
   **not** wait for the bootstrap to run, so:

   ```
   tofu apply       -> "Apply complete! 8 added, 3 changed"   PASS
   SSM association  -> Failed                                  (nobody notices)
   ```

   Three genuine failures that day (stale `main` branch with no app directory;
   `git checkout` on a shallow single-branch clone; a port conflict leaving the
   new Caddy stuck in `Created`) **all reported a successful apply.** In a CD
   pipeline every one of those ships a green checkmark over a broken deploy.

   Every deploy job must therefore, after `apply`:

   1. `aws ssm send-command` the bootstrap document (or
      `start-associations-once`) and capture the **command id**.
   2. **Poll to completion** — `aws ssm wait command-executed`, or a loop on
      `get-command-invocation` until the status leaves `Pending`/`InProgress`.
   3. **Fail the job** on any status other than `Success`, and print
      `StandardErrorContent` into the run log so the cause is visible without
      SSH.
   4. **Verify the app actually serves** — poll the health endpoint until it
      returns 200, with a timeout. A container can start and still be broken.
   5. Only then write `/wusool/<env>/<stack>/deployed_sha`. Recording it before
      verification would make a failed deploy look deployed to the next run's
      change detection.

   Without this the pipeline is not a deploy pipeline — it is a config-push
   pipeline that hopes for the best.

   **Rolling the app is a separate step — do not forget it.** `tofu apply`
   re-registers `aws_ssm_document.bootstrap` with the new digest, but
   `aws_ssm_association` does **not** re-run on its own. The workflow must then
   call `aws ssm send-command` (or `start-associations-once`) against the
   instance, or the new image is registered and never actually deployed. This is
   the same class of trap as Defect 1 — a document that is registered but not
   applied.

   **Trade-off accepted:** passing digests as `-var` rather than committing them
   to `envs/*.tfvars` means a reviewer sees no digest diff on the promotion PR.
   The review becomes the `dev -> prod` **code** diff instead — more informative
   than a hash, but it is a deliberate change from a digest-pinning design.
   ECR tags and the `/wusool/<env>/<stack>/deployed_sha` SSM parameter remain the
   record of what is running where.

   Requires ECR `imageTagMutability = IMMUTABLE`, so `sha-<SHA>` cannot be
   repointed at different content after dev has validated it.

   **This removes `git_ref` and `github_token` from the instance entirely.**
   Today the box clones a branch, so `git_ref` is a per-environment tfvars value
   (`dev` for dev, `prod` for prod) — necessary, but transitional. Under ECR the
   instance never clones: CI checks out whichever branch triggered it
   (`github.ref`) and the instance pulls a pinned digest. Hotfixes work the same
   way — CI builds from `hotfix/**` and the instance deploys that digest — so no
   branch name ever reaches the instance, and the GitHub PAT that leaked on
   2026-08-16 stops being needed at all.

3. **Rewrite `modules/matching-engine-ec2/user_data.sh.tpl`**: delete the
   `git clone` and `docker compose build`; the generated compose uses
   `image: <acct>.dkr.ecr.<region>.amazonaws.com/<repo>@<digest>`. Drop
   `git_repo_url` / `git_ref` / `github_token`; add an `image_digest` variable
   and `ecr:GetAuthorizationToken` + pull permissions on the instance role.
   **No NAT or VPC endpoint needed** — instances are in the public subnet with
   EIPs (`dev/main.tf:18,48`).
4. **Create `/wusool/prod/matching-engine`** — it has never existed. Forces a
   decision: **one Slack app across both envs, or a separate prod app?**
   Recommended separate; a shared app means dev experiments post into prod
   channels.
5. Create `stacks/postgres` and `stacks/matching-engine` for **prod** with
   `envs/prod.tfvars`. Prod gains a database and an application for the first
   time. Promotion: deploy digest D to dev → verify → merge `dev -> main` → the
   same digest D deploys to prod.
6. Rollback becomes an apply with the previous digest — seconds, and it cannot
   fail to build.
7. **Pin n8n's images while here**: `docker.n8n.io/n8nio/n8n`,
   `n8nio/runners:latest`, and `caddy:2` are all unpinned **in live prod
   right now** (confirmed in the decoded document). A container restart can
   silently upgrade n8n in production.

---

### Phase G — Alembic with SQLAlchemy models as source of truth

Per the decision to model all ~22 tables.

1. **Pick the model home.** Recommended: models live in `database/`, and the app
   imports them — inverting today's direction so the DDL owner is unambiguous.
   `database/` becomes a package (`pyproject.toml`, `alembic.ini`,
   `migrations/versions/`) sharing the `DeclarativeBase` currently at
   `workflows/wusool-toolkit/matching-engine/app/shared/database/base.py`.
2. **Sequencing against Phase F**: if the app imports from `database/`, the
   matching-engine Docker build context must widen past
   `workflows/wusool-toolkit/matching-engine/`, and `database/` must become an
   installable dependency in its `pyproject.toml`/`uv.lock`. Phase F moves that
   build into CI — **decide the model home before Phase F's Dockerfile rewrite**
   or the two phases fight.
3. **Write the 13 missing models.** Existing (9 tables): `organizations`,
   `people`, `deals`, `mandates`, `meetings`, `buyer_roles`, `seller_roles`,
   `match_scores`, `match_results`. Missing: `users`, `investor_lender_roles`,
   `activities`, `deal_stage_events`, `signals`, `buyer_intel`,
   `seller_financials`, `mandate_targets`, `documents`, `vertical_kb`,
   `graph_edges`, `attio_sync_state`, `attio_raw_events`, `scorecards`.
   **Until all are modelled, autogenerate will propose DROPping the unmapped
   ones.**
4. **Baseline revision `0001`** is generated against the live dev database and
   then **`alembic stamp`ed, not applied** — the tables already exist.
5. **Hand-write what autogenerate cannot see**: the `pgvector` extension guard
   (`001`), the three enums and the `scribe_pub` role + GRANTs (`005`), the
   trigram GIN index (`007`).
6. **Scribe needs no coordination on ownership** — it applies no migrations and
   holds only `scribe_pub` data grants, so wusool-infra owns all DDL. Do carry
   the `scribe_pub` role + GRANTs into a hand-written revision, and tell scribe
   before any `meetings` column change ships. See Part 2.
7. Delete `database/sql/00*.sql` only after `alembic upgrade head` on an empty
   database produces a schema that `schema_check.py` reports as identical to
   live. Keep the files until then.
8. `database/setup-postgres.ps1` becomes a thin wrapper around
   `alembic upgrade head`, keeping its `current_database() == 'wusool_crm'` guard.

**Note:** prod has no database today. `stacks/postgres` for prod (Phase F step 5)
must exist before prod migrations mean anything.

---

---

### Phase H — Durability: retire the AMI tripwire and make instances disposable

The root problem: `data "aws_ami" { most_recent = true }` resolves to the newest
AL2023 on every plan, and `lifecycle { ignore_changes = [ami] }` hides it. Net
effect — **the instances are frozen forever** on `ami-0011111f781020765` (prod
n8n) and `ami-04bc554a9635a77c8` (scribe), receiving no AMI-level patching,
while the single lifecycle block is the only thing preventing total data loss.
It fails silently if anyone removes it, runs `tofu taint`/`-replace`, or forgets
to copy it into the new stacks in Phase D.

You cannot update the AMI, and the thing preventing the update is also the only
thing preventing data loss. Phase H cuts that knot.

#### H1. Pin the AMI explicitly *(do early — cheap, removes the silent freeze)*

Replace `most_recent = true` + `ignore_changes` with an explicit `ami_id`
variable set per environment in `envs/*.tfvars`, seeded with the AMI each
instance runs today.

- AMI changes become a **visible, reviewed tfvars diff** instead of hidden drift.
- OS patching decouples from AMI replacement — patch in place via an SSM
  `dnf update` association on a schedule.
- Keep `ignore_changes = [ami]` as belt-and-braces until H2 lands.

#### H2. Move n8n's state into Postgres — the real fix

**Recommended over adding data volumes.** A separate EBS volume per service
would cost ~$2–5/month each and **cannot be shared** — EBS attaches to one
instance at a time, and n8n, matching-engine and scribe are on three different
instances. (`io2` Multi-Attach needs a cluster-aware filesystem; EFS is
unsuitable because n8n's store is SQLite, and SQLite over NFS has known locking
bugs that risk corruption.)

**The shared durable store already exists: RDS.** matching-engine already uses
it; scribe already uses it plus S3. Only n8n is the outlier, sitting on SQLite
on a local disk.

Migrate n8n to `DB_TYPE=postgresdb` against the existing RDS instance:

- The instance becomes **disposable** — replacement stops being a data event, so
  AMI updates become routine and H1's tripwire disappears.
- Backups come **free** from RDS (7-day automated, `deletion_protection = true`,
  final snapshot on — already configured).
- No service needs a data volume at all.
- Opens a path to blue/green deploys later.

##### Cutover procedure — `DB_TYPE=postgresdb` alone does NOT move existing data

Setting the env var points n8n at an **empty** database. n8n ships no in-place
SQLite→Postgres converter; the supported path is export/import via its CLI.
Rehearse the whole thing on dev first.

**Prerequisites**
- `stacks/postgres` exists for the target environment (**prod has no database
  until Phase F** — sequence accordingly).
- A dedicated database + role for n8n (do **not** reuse matching-engine's).
- Credentials written to `/wusool/<env>/n8n` under `env` so the bootstrap injects
  them: `DB_TYPE`, `DB_POSTGRESDB_{HOST,PORT,DATABASE,USER,PASSWORD}`.
- SG ingress: n8n's SG → Postgres:5432 (via the self-attach pattern in D4a).
- **`N8N_ENCRYPTION_KEY` set explicitly and identical to the stored value**
  (Defect 4). A different key makes every imported credential undecryptable.

**Maintenance window** — webhooks are down for the duration. Announce it; n8n
webhook endpoints are called by external systems.

```bash
# 1. fresh snapshot immediately before (see Step 0 for the pattern)
# 2. stop the schedulers/webhooks but keep the container up for the CLI
docker compose exec n8n n8n export:workflow    --all --output=/home/node/wf.json
docker compose exec n8n n8n export:credentials --all --output=/home/node/cred.json
#    ^ credentials stay ENCRYPTED; they are only readable with the same key
docker compose cp n8n:/home/node/wf.json   ./wf.json
docker compose cp n8n:/home/node/cred.json ./cred.json

# 3. switch env to postgres, recreate, then import
docker compose down && docker compose up -d
docker compose exec n8n n8n import:workflow    --input=/home/node/wf.json
docker compose exec n8n n8n import:credentials --input=/home/node/cred.json
```

**Accept this loss up front:** `export:workflow`/`export:credentials` carry
workflows and credentials **only**. *Execution history is not migrated.* If that
history matters, archive the SQLite file from the snapshot before cutover.

**Verification — all of these, not just one**
- Workflow count in the UI matches the pre-cutover count.
- A credential **opens and decrypts** in the UI (proves the key carried).
- One workflow **executes successfully end to end**.
- A webhook URL still resolves and fires from outside.
- `SELECT count(*) FROM workflow_entity;` in Postgres is non-zero.
- The SQLite file is no longer being written (`ls -l` mtime stops advancing).

**Rollback** — cheap, because nothing is destroyed: revert the env vars to
SQLite and `docker compose up -d`. The original SQLite file is untouched on the
volume throughout. **Do not delete it for at least one full business cycle**
after cutover.

**Rollback triggers:** credentials fail to decrypt, workflow count mismatch, any
webhook not firing, or the window expiring — roll back rather than debugging live.

**Sequencing:** prod has no database until Phase F creates `stacks/postgres` for
prod. Do dev first, prove it, then prod after F.

#### H3. Scheduled backups — there are none today

**Recommended (pending confirmation):** an `aws_backup_plan` in `stacks/account`
— daily at 03:00 UTC, 30-day retention, resource selection by tag
`Backup = true`, covering EC2 root volumes and RDS under one auditable policy.
A DLM policy is a lighter alternative but covers EBS only.

Whichever is chosen, **test a restore once** — an untested backup is a
hypothesis, not a backup.

Scribe is better positioned than n8n: it already keeps durable state in
`wusool-scribe-artifacts` (S3) and SQS. Confirm with its owner whether anything
durable sits on its root volume; if not, scribe needs H1 only.

---

## Part 2 — Handover document for the `scribe` repo

> **Extracted to `SCRIBE_INFRA_CONTRACT.md` in this repo** — hand that file to
> the scribe repo owner. This section remains the source of truth; if you edit
> it, regenerate the extract rather than editing both.

### What changed and why you're reading this

`wusool-infra` has been restructured so that every service is defined **once**
and deployed to `dev` or `prod` by swapping a backend key and a var-file. Scribe
is currently deployed to dev only, from its own state, outside that convention.
Following this contract lets you stand up **scribe dev and scribe prod** the
same way every other service works.

### Where scribe stands today (verified live)

| Fact | Value |
|---|---|
| Instance | `wusool-scribe` / `i-01bf509a92ed1dcba`, **c6a.xlarge** |
| VPC | `vpc-0ed8db2cc2b5f2cdc` — **the dev VPC** |
| Security group | `sg-0684b8cf83abfd065` (`wusool-scribe-instance`) |
| State | `s3://wusool-tfstate/wusool/dev/scribe/terraform.tfstate`, serial 15, written by 1.10.6 |
| Structure | Flat root module — all resources at root, no `module` blocks |
| Secret | `/wusool-scribe` |
| Owns | EC2, SGs, S3 buckets, SQS queue, Secrets Manager secret, SSM document |
| Tags | **No `Environment` tag** |
| Database | Writes `meetings` in `wusool_crm` via the least-privilege `scribe_pub` role; has its own Alembic chain |

Good news: **your backend key already matches the new convention**
(`wusool/<env>/<service>/terraform.tfstate`). Scribe is the existing precedent
that per-service state works here.

### The contract — what scribe must do to plug in

**1. Toolchain.** Match the version pinned in
`wusool-infra/terraform/.opentofu-version`. Your state is at 1.10.6 while
wusool-infra's is at 1.15.6. **Do not let anyone apply scribe's state with the
newer binary before you have decided to upgrade** — it upgrades the state in
place and your current tooling may stop reading it.

**2. Backend keys.** Keep the existing dev key; add prod:

```
wusool/dev/scribe/terraform.tfstate      # exists
wusool/prod/scribe/terraform.tfstate     # new
```

Bucket `wusool-tfstate`, **region `me-central-1`** (state region deliberately
differs from the resource region — do not "fix" it). Use `use_lockfile = true`;
there is no DynamoDB lock table.

**3. One stack, two environments.** Replace any env-specific directories with a
single root using a partial backend:

```hcl
terraform { backend "s3" {} }
```

```bash
tofu init -reconfigure \
  -backend-config="bucket=wusool-tfstate" \
  -backend-config="region=me-central-1" \
  -backend-config="key=wusool/$ENV/scribe/terraform.tfstate" \
  -backend-config="use_lockfile=true" -backend-config="encrypt=true"
tofu apply -var-file=envs/$ENV.tfvars
```

Commit `envs/dev.tfvars` and `envs/prod.tfvars`. Non-secret values (region,
CIDRs, instance type, domains) **belong in git** — they are configuration, not
secrets. Their absence from version control is precisely how wusool-infra's prod
drift went unnoticed.

**4. Stop creating your own network. Consume the base layer.**

Scribe currently runs inside the dev VPC with its own SGs. Under the new model,
networking is owned by `stacks/base` per environment. Read it:

```hcl
data "terraform_remote_state" "base" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/base/terraform.tfstate"
    region = "me-central-1"
  }
}
```

Available outputs: `vpc_id`, `public_subnet_id`, `private_subnet_id`,
`database_private_subnet_ids`, `alarm_topic_arn`.

Use `alarm_topic_arn` for your CloudWatch alarms rather than creating a second
SNS topic. **Do not create a GuardDuty detector or enable SecurityHub** — they
are account-level singletons already owned by `stacks/account`, and a second one
will fail the apply.

**5. Attach yourself to Postgres — don't ask to be added to a list.**

`wusool-infra` currently hardcodes `"sg-0684b8cf83abfd065"` (your dev SG) in the
RDS ingress allow-list. Under the new model that inverts: **`stacks/postgres`
exports its SG ID and owns no allow-list; each consumer creates its own ingress
rule.** In scribe's stack:

```hcl
data "terraform_remote_state" "postgres" {
  backend = "s3"
  config = {
    bucket = "wusool-tfstate"
    key    = "wusool/${var.environment}/postgres/terraform.tfstate"
    region = "me-central-1"
  }
}

resource "aws_vpc_security_group_ingress_rule" "postgres" {
  security_group_id            = data.terraform_remote_state.postgres.outputs.security_group_id
  referenced_security_group_id = aws_security_group.scribe.id
  from_port                    = 5432
  to_port                      = 5432
  ip_protocol                  = "tcp"
  tags = { Name = "scribe-${var.environment}", Consumer = "scribe" }
}
```

**This is the answer to "do I have to add the SG per environment?" — no.** The
same code, applied with `dev.tfvars` or `prod.tfvars`, reads that environment's
Postgres SG and attaches that environment's scribe SG. Nobody edits
`wusool-infra`, and nobody pastes an SG ID.

Also export your own SG so other services can reference it:

```hcl
output "security_group_id" { value = aws_security_group.scribe.id }
```

Apply order per environment: `base` → `postgres` → `scribe`.

**6. Naming and tagging.** Every resource: `wusool-<env>-scribe-<thing>`.
Set `default_tags` in the provider — `Project`, `Environment`, `ManagedBy =
"terraform"`, `Owner`. Scribe's instance currently has **no `Environment` tag**,
which is why it doesn't show up in environment-filtered queries and cost reports.

**7. Rename the secret.** `/wusool-scribe` → `/wusool/<env>/scribe`, matching
`/wusool/dev/n8n`, `/wusool/prod/n8n`, `/wusool/dev/matching-engine`. Scribe prod
needs its own secret; **do not share the dev secret across environments.**

**8. Never bake a script into an SSM document and re-run the stale copy.**

This is the most expensive lesson in this account. `aws_ssm_document.bootstrap`
holds an *embedded copy* of the rendered `user_data` frozen at the last apply.
Re-running it regenerates config from that stale copy and silently reverts live
fixes. **It has broken wusool-infra's production three times**, and as of this
survey the registered prod n8n document still pointed at a hostname retired in
August — invoking it would have taken production down.

Scribe has the identical structure. The invariants:
- The bootstrap document **must be re-registered from current source as part of
  every deploy**.
- A deploy path of "re-run the existing document" must never be the *only*
  option.
- If you ship an app-redeploy workflow that only calls `ssm send-command`,
  **document explicitly** that it cannot pick up a template change without an
  apply first.

**9. Build once, deploy by digest.** Do not `git clone` + `docker build` on the
instance. Build in CI, push to ECR, deploy by `sha256:` digest, so dev and prod
run the identical artifact. Instances are in the public subnet with EIPs, so no
NAT or VPC endpoint is required. Pin every base image.

**10. Branching and CD.** `dev` + `prod`. Merge to `dev` deploys dev; merge to
`prod` deploys prod. Plan-on-PR is a required status check on **both** branches,
and the plan must select its var-file from the PR's **base** branch — otherwise
your promotion PR shows a dev diff while prod is what changes. Use GitHub OIDC
(role ARNs from `stacks/account`); no static AWS keys.

**11. Database — DDL ownership is settled; scribe is a data client only.**

**wusool-infra owns 100% of `wusool_crm` DDL.** Scribe has read/write on the
`meetings` *data* via the least-privilege `scribe_pub` role and **applies no
migrations**. Keep it that way:

- Scribe must **not** run Alembic, `CREATE TABLE`, or `ALTER TABLE` against
  `wusool_crm`. Two migration chains on one database corrupt each other's
  version table.
- Scribe's DB user keeps `scribe_pub` only. Do not grant DDL.
- **If scribe needs a schema change to `meetings`, request it in wusool-infra**
  — it lands as an Alembic revision there. Treat the schema as an API owned by
  another team.
- wusool-infra carries the `scribe_pub` role and its GRANTs (currently
  `database/sql/005_meetings.sql`) into a hand-written Alembic revision, since
  autogenerate cannot see roles or grants.
- Scribe should keep a **read-only** drift check (reflect the live schema,
  assert the columns it depends on still exist) so a wusool-infra migration that
  breaks scribe fails loudly in scribe's CI rather than at runtime.

**Sequencing: prod has no database yet.** `wusool-infra`'s `stacks/postgres` for
prod is created in its Phase F. **Scribe prod cannot be deployed until that
exists.**

### Checklist to add scribe dev + prod

- [ ] Toolchain is **OpenTofu**, version matching `wusool-infra/terraform/.opentofu-version`
- [ ] Single root with partial backend; `envs/dev.tfvars` + `envs/prod.tfvars` committed
- [ ] Consumes `stacks/base` remote state for VPC/subnets/SNS
- [ ] Creates no GuardDuty detector and does not enable SecurityHub
- [ ] Exports `security_group_id`
- [ ] `wusool-<env>-scribe-*` naming; `default_tags` incl. `Environment`
- [ ] Secret renamed to `/wusool/<env>/scribe`; separate secret per env
- [ ] SSM document re-registered from source on every deploy
- [ ] Image built in CI, pushed to ECR, deployed by digest; base images pinned
- [ ] OIDC auth; plan-on-PR required on `dev` and `prod`, var-file from base ref
- [ ] DDL ownership agreed (a/b/c above) and written down
- [ ] `stacks/postgres` prod exists before scribe prod is applied

---

## Appendix — fix by construction

Fold into whichever phase touches the file; do not schedule separately.

| Issue | Location |
|---|---|
| Hardcoded SG `"sg-0684b8cf83abfd065"` (= `wusool-scribe-instance`) | `dev/main.tf:93` → consumers attach themselves (D4a); requires converting `postgres-rds` off inline `ingress` |
| `templatefile()` rendered twice — two places to drift | `modules/n8n-ec2/main.tf:151-157` and `195-201` → one `local`, as matching-engine already does |
| Single-hostname Caddyfile — **confirmed in the decoded prod document**; root cause of a prior incident | `modules/n8n-ec2/user_data.sh.tpl` |
| Unpinned images — **confirmed live in prod**: `docker.n8n.io/n8nio/n8n`, `n8nio/runners:latest`, `caddy:2` | `modules/n8n-ec2/user_data.sh.tpl` |
| `arm64` accepted by validation but `docker-compose-linux-x86_64` hardcoded — **confirmed in the decoded document** | both `user_data.sh.tpl` files |
| Orphaned DynamoDB lock table `wusool-tfstate-locks` — **live table DELETED 2026-08-15**; code references remain | `bootstrap/main.tf:55-63`, `bootstrap/outputs.tf:6-9` — see D0a |
| `terraform/bootstrap/` state is lost; the state bucket is unmanaged | adopt bucket into `stacks/account` with `prevent_destroy`, delete `bootstrap/` — see D0a |
| Orphaned empty VPCs `n8n-dev-vpc` / `n8n-prod-vpc` in `me-central-1` | live account only |
| `README.md:~256` claims prod uses DynamoDB locking — stale | `terraform/environments/dev/README.md` |
| Env-specific defaults inside modules (`aws_region`, `git_repo_url`, `db_name`, `n8n_timezone`) | `modules/*/variables.tf` → move to `envs/*.tfvars` |
| `ami_architecture` validation present in prod, missing in dev | resolved by one stack existing |
| CloudTrail policy formatted differently per env, invisible to `fmt -check` | resolved by `stacks/base` existing |
| Prod less hardened than dev (no GuardDuty/SecurityHub) | resolved by `stacks/account` |

`crm-sync` and `bedrock-ai` get **`ci.yml` lint coverage only and no stack** —
both are operator PowerShell run from a workstation with no runtime, image, or
AWS resource of their own. The "one dev + one prod per service" rule applies to
n8n, postgres, matching-engine, and scribe.

---

## Verification

| Phase | Test |
|---|---|
| A | `init` + `plan` succeed against real backends for dev and prod with no "state written by a newer version" error |
| B | Decoded `aws_ssm_document.bootstrap.content` contains `n8n.wusoolcapital.com` and **zero** `n8n-prod.wusoolcapital.com`; live site still serves HTTPS |
| C | Branch protection is actually settable (i.e. Defect 6 resolved) or the gap is explicitly accepted in writing; `guard-prod-history.yml` fails a deliberately squash-merged test commit on `prod`; `dev` is default; `prod` exists, branched from `dev`; plan check required on `dev` **and** `prod`; no `Azmora-ai` references remain |
| D | `git check-ignore -v terraform/envs/dev.tfvars` returns nothing (D0b). `stacks/account` adopts `wusool-tfstate` **and its three subordinate resources** with a clean plan and `prevent_destroy` set; `terraform/bootstrap/` deleted; lock table removed. EBS snapshots exist and are `completed` before starting. After every `state mv`: the SOURCE state lists **zero** moved resources and the DESTINATION lists them, both verified with `state list`. Every stack × env: `plan` reports `0 to add, 0 to change, 0 to destroy` and zero `forces replacement`. `lifecycle { ignore_changes = [ami] }` present in the new n8n stack. `terraform/environments/` deleted once green. `stacks/base` outputs resolve in service stacks. n8n stays reachable; dev matching-engine `/health` stays green. SecurityHub finding history intact |
| E | PR touching only `stacks/n8n/**` → matrix contains `n8n` only. PR touching `modules/network/**` → fans out to `base` + downstream. **A `dev -> prod` PR comments a plan naming the prod backend key.** Broken Python fails `ci.yml`. Deleting the SSM `deployed_sha` triggers a full deploy |
| F | A single merge to `dev` builds, applies **and rolls** the app — verify the running container digest changed, not just the SSM document. `build-push.yml` has **no `prod` trigger**. After promotion, `docker inspect` on dev and prod report the **same image digest**. A commit pushed directly to `prod` with no matching ECR image **fails the deploy** rather than silently deploying something stale. Rollback: dispatch with the previous digest and the app serves traffic again |
| H | `ami_id` is an explicit tfvars value; changing it shows a reviewed diff. After H2, all of: workflow count matches pre-cutover, a credential decrypts in the UI, one workflow executes end to end, a webhook fires from outside, `select count(*) from workflow_entity` is non-zero, and terminating/recreating the instance loses no data. A restore from the backup plan has been tested at least once. |
| G | `alembic upgrade head` on empty Postgres → `schema_check.py` reports zero drift vs live dev. `alembic check` clean. Second `upgrade head` is a no-op |

---

## Accepted risks (declined guardrails — recorded deliberately)

0. **Nothing is currently enforced at all (Defect 6).** On the free/private
   plan there is no branch protection, no required status check, no restriction
   on merge method, and no block on direct pushes to `prod`. Every guardrail
   below is convention plus post-hoc detection until the org moves to GitHub
   Team. **This supersedes the risk framing of items 1 and 2** — they assume a
   PR review actually gates the merge, which today it does not.

1. **No approval gate on prod.** A merge to `prod` applies to production with no
   human confirmation between the merge click and AWS changing. The plan
   reviewed on the PR may differ from the plan applied, if anything else merged
   in between.

   *Recommended mitigation that costs no extra click:* have the prod apply job
   run `plan -detailed-exitcode` and **hard-fail if the plan contains any
   resource destruction**, unless dispatched with an explicit
   `allow_destroy: true`. Automated, not a human gate, and it catches the
   specific catastrophic case the approval gate existed to catch.

2. **No dev-ancestry check.** Any commit reaching `prod` deploys to prod,
   including a hotfix that never ran in dev. `backmerge.yml` prevents such a fix
   being *lost*, but not from being *untested* when it first reaches production.

3. **Option B ingress splits the allow-list across repos.** With consumers
   attaching themselves to Postgres, no single file lists everyone with database
   access. Mitigate by tagging every rule with its consumer and auditing with
   `aws ec2 describe-security-group-rules` in a periodic check.

*(Resolved since first draft: scribe applies no migrations and holds only
`scribe_pub` data grants, so wusool-infra owns all DDL outright — the
two-Alembic-chain risk does not exist.)*
