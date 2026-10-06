# Contributing

All changes must enter the `dev` branch through a reviewed pull request.
Do not push commits directly to `dev` or merge your own pull request without
approval.

## One-time setup

```powershell
git remote -v
git fetch origin --prune
```

The repository remote should be:

```text
https://github.com/wusool-capital/wusool-infra.git
```

## Start a change

Always branch from the latest remote `dev`:

```powershell
git fetch origin --prune
git switch dev
git pull --ff-only origin dev
git switch -c feature/short-description
```

Use `fix/short-description` for bug fixes and
`docs/short-description` for documentation-only changes.

## Toolchain

This repository is managed with **OpenTofu**, not HashiCorp Terraform. The
version is pinned in `infrastructure/terraform/.opentofu-version` and CI
installs exactly that version — keep your local install matching it.

```bash
brew install opentofu     # macOS; see opentofu.org/docs/intro/install for others
tofu version              # must match infrastructure/terraform/.opentofu-version
```

Do not run `terraform` against this repository. The two tools write different
provider registries into `.terraform.lock.hcl` and stamp different versions into
state, so mixing them causes avoidable churn and, in the worst case, a state
another contributor's tooling cannot read.

## Review and validate locally

```powershell
git status
git diff
Set-Location infrastructure/terraform
tofu fmt -check -recursive
Set-Location ../..

Set-Location infrastructure/terraform/stacks/base   # repeat per changed stack: n8n, toolkit, postgres, peering, account
tofu init -backend=false
tofu validate
Set-Location ../../../..
```

Repeat `tofu init -backend=false` and `tofu validate` for every changed stack,
including `scribe-updates`. Do not initialize a remote backend for local
validation.

For changes under `server/`, run from `server/`:

```bash
uv run ruff check .
uv run ruff format --check .
uv run ty check .
uv run pytest
uv run alembic check       # when models or migrations changed
```

For migration or model changes, the database schema workflow also runs the
single-head check, upgrades a disposable PostgreSQL database, and checks model
drift. Resolve multiple migration heads in a reviewed PR before merging.

For PowerShell or shell-script changes, run the applicable PowerShell quality
and shell-test workflows. Their repository entry points are
`Invoke-ScriptAnalyzer` and `./checks.sh shell` from `server/` respectively.

For changes to the published GitBook documentation, install Vale and run
the same check CI runs from `server/`:

```bash
brew install vale
./checks.sh docs
```

It fails on any Vale warning in lines your branch added. Running bare `vale`
lists warnings but still exits 0, so it won't catch what CI blocks.

Follow the page templates and content budgets in
[`docs/internal/dev/DOCUMENTATION_STYLE_GUIDE.md`](docs/internal/dev/DOCUMENTATION_STYLE_GUIDE.md).

When OpenTofu infrastructure architecture changed:

```text
Use $sync-terraform-docs
```

Review the generated documentation before committing.

## Commit and push

```powershell
git status
git add <files belonging to this change>
git diff --cached
git commit -m "<type>(api): 4–8 word message"
git push -u origin HEAD
```

Use one of `feat`, `fix`, `docs`, `chore`, or `refactor` for `<type>`. Stage
only files belonging to the change.

`git push -u origin HEAD` pushes the current feature branch. It does not push
directly to `dev`.

## Open the pull request

After pushing, open the repository in GitHub:

1. Select the pushed feature branch.
2. Click **Compare & pull request**.
3. Set the base branch to `dev`.
4. Complete the pull-request template.
5. Add an authorized reviewer.
6. Create the pull request and wait for all applicable required checks. These
   may include OpenTofu, Python quality/tests, database schema, PowerShell,
   shell, and documentation checks depending on the changed paths.

The pull request may merge only after:

1. All applicable required CI checks succeed.
2. The branch is up to date with `dev`.
3. At least one authorized reviewer approves it.
4. All review conversations are resolved.

After approval and successful checks, use the GitHub pull-request page to
**Squash and merge**. Branch protection remains the authority and blocks the
merge until all requirements pass.

## Keep a pull request current

```powershell
git fetch origin --prune
git rebase origin/dev
git push --force-with-lease
```

Use `--force-with-lease` only on your own feature branch, never on `dev`.

## After merge

```powershell
git switch dev
git pull --ff-only origin dev
git branch -d feature/short-description
git fetch origin --prune
```

## One-time `dev` branch protection

A repository administrator must configure a ruleset or branch protection rule
for `dev` in GitHub:

1. Open **Settings → Rules → Rulesets → New branch ruleset**.
2. Target the branch `dev`.
3. Enable **Require a pull request before merging**.
4. Require at least **1 approval**.
5. Enable **Dismiss stale pull request approvals when new commits are pushed**.
6. Enable **Require review from Code Owners** after adding real owners to
   `.github/CODEOWNERS`.
7. Enable **Require status checks to pass**.
8. Select these required checks:
   - `OpenTofu Format`
   - `OpenTofu Validate (infrastructure/terraform/stacks/account)`
   - `OpenTofu Validate (infrastructure/terraform/stacks/base)`
   - `OpenTofu Validate (infrastructure/terraform/stacks/n8n)`
   - `OpenTofu Validate (infrastructure/terraform/stacks/toolkit)`
   - `OpenTofu Validate (infrastructure/terraform/stacks/postgres)`
   - `OpenTofu Validate (infrastructure/terraform/stacks/peering)`
   - `OpenTofu Validate (infrastructure/terraform/stacks/scribe-updates)`
   - `Python quality (required)`
   - `Python unit tests (required)`
   - `Python integration tests (required)`
   - `Database schema (required)`
   - `Shell tests (required)`
9. Enable **Require branches to be up to date before merging**.
10. Enable **Require conversation resolution before merging**.
11. Enable **Block force pushes** and **Block deletions**.
12. Do not add bypass actors unless an emergency process requires them.

The workflow file validates changes, while the GitHub ruleset prevents merging
when validation or approval is missing.

## Operational documentation

For production incidents, consult and maintain the relevant guide under
`docs/runbooks/`. When a problem is resolved, create a new redacted postmortem under
`docs/postmortems/` using [`docs/postmortems/README.md`](docs/postmortems/README.md).
