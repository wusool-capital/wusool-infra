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
https://github.com/Azmora-ai/wusool-infra.git
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

## Review and validate locally

```powershell
git status
git diff
terraform fmt -check -recursive

Set-Location environments/dev
terraform init -backend=false
terraform validate
Set-Location ../..
```

When Terraform architecture changed:

```text
Use $sync-terraform-docs
```

Review the generated documentation before committing.

## Commit and push

```powershell
git status
git add --all
git diff --cached
git commit -m "Describe the infrastructure change"
git push -u origin HEAD
```

`git push -u origin HEAD` pushes the current feature branch. It does not push
directly to `dev`.

## Open the pull request

After pushing, open the repository in GitHub:

1. Select the pushed feature branch.
2. Click **Compare & pull request**.
3. Set the base branch to `dev`.
4. Complete the pull-request template.
5. Add an authorized reviewer.
6. Create the pull request and wait for Terraform CI.

The pull request may merge only after:

1. Terraform CI succeeds.
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
   - `Terraform Format`
   - `Terraform Validate (bootstrap)`
   - `Terraform Validate (environments/dev)`
   - `Terraform Validate (environments/prod)`
9. Enable **Require branches to be up to date before merging**.
10. Enable **Require conversation resolution before merging**.
11. Enable **Block force pushes** and **Block deletions**.
12. Do not add bypass actors unless an emergency process requires them.

The workflow file validates changes, while the GitHub ruleset prevents merging
when validation or approval is missing.
