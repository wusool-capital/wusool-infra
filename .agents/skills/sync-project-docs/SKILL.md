---
name: sync-project-docs
description: Keep the repo-wide documentation set synchronized with the actual state of the code, scripts, and Terraform — CHANGELOG.md, docs/operations/, docs/technical/, docs/user-guide/, and every README not owned by sync-terraform-docs or sync-crm-schema-docs. Use after finishing a unit of work (Terraform change, migration milestone, new script, new workstream, a user-facing behaviour change), whenever asked to refresh/update/sync documentation, and before ending a session that changed tracked files.
---

# Sync Project Docs

Repo-wide sibling of `sync-terraform-docs` (Terraform architecture READMEs +
diagrams) and `sync-crm-schema-docs` (the CRM data-model docs). This skill
owns everything else:

1. **`CHANGELOG.md`** — append meaningful changes under a dated heading,
   newest first, grouped Added / Changed / Fixed / Removed. One or two lines
   each, referencing the PR number. Not a diary — skip routine churn.
2. **`docs/operations/`** — the current delivered state and operational
   handover. Update environments, deployment and recovery procedures,
   monitoring, ownership, dependencies, and open items when they change.
3. **`docs/technical/`** — platform architecture plus one consolidated
   technical reference per product. Update the affected product page when a
   module, service, API, configuration value, or data flow changes.
4. **`docs/user-guide/`** — one consolidated guide per product. Update the
   affected page when a user-visible workflow, command, rule, or limit changes.
5. **`docs/README.md`** — the docs index; update if a page is added or removed.
6. **Every other README** not owned by the sibling skills — root `README.md`
   non-Terraform sections, `server/README.md` and the module READMEs under
   `server/app/modules/*/`, `server/SCHEMA.md`,
   `infrastructure/crm-sync/scripts/*/README.md`,
   `server/scripts/postgres-sync/README.md`.

## Workflow

1. If Terraform files changed, run `sync-terraform-docs` first (or note that
   it should be run). If Attio/Postgres schema changed, run
   `sync-crm-schema-docs`. Do not duplicate their work here.
2. Diff recent changes against documentation:
   ```powershell
   git log --oneline -20
   git diff --stat HEAD~5 2>$null
   ```
   Identify what actually changed: new/removed scripts, new modules, migration
   milestones, schema changes, a new external service, a changed deploy step,
   a user-visible bot change.
3. For each README in scope, compare its claims against the files it
   describes (file names, flags, commands, prerequisites, directory trees).
   Correct anything stale. Do not invent capability that isn't in the code.
4. Add a `CHANGELOG.md` entry for anything meaningful, and reflect it in
   `docs/operations/delivery-status.md` and the affected technical or user
   guide where relevant.
5. Run, if Terraform or scripts changed:
   ```powershell
   tofu fmt -check -recursive
   git diff --check
   ```
6. Report what changed, or say explicitly that nothing needed updating.

## Source-of-truth rules

- Code, scripts, and Terraform are the source of truth — not this skill's
  memory of a previous session, and not chat history.
- For the Attio/PostgreSQL migration workstream, defer to the detailed
  decision log referenced in `AGENTS.md` for field-level claims.
- Never copy secrets, credentials, personal emails, or IP addresses into any
  document. (`infrastructure/terraform/envs/*.tfvars` values that are already
  committed and non-secret are fine to reference.)
- If unsure whether something is done vs. in progress, mark it as in progress
  and say why in the report — do not guess.
