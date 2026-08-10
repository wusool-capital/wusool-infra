---
name: sync-project-docs
description: Keep every README in the repository and the top-level PROGRESS.md status file synchronized with the actual state of the code, scripts, and Terraform. Use after finishing a unit of work (Terraform change, migration milestone, new script, new workstream), whenever asked to refresh/update/sync documentation or progress, and before ending a session that changed tracked files.
---

# Sync Project Docs

This is the repo-wide sibling of `sync-terraform-docs`: that skill owns
Terraform-specific documentation (architecture READMEs, network diagrams).
This skill owns two additional things:

1. **`PROGRESS.md`** at the repository root — the single file a new session
   should read to know "what has been done so far" without reconstructing it
   from git log or chat history.
2. **Every other README** in the repo that isn't already covered by
   `sync-terraform-docs` (e.g. `scripts/attio/README.md`, `scripts/db/README.md`,
   `environments/dev/README.md`, root `README.md` sections that aren't purely
   Terraform architecture).

## Workflow

1. If Terraform files changed, run `sync-terraform-docs` first (or note that
   it should be run) — do not duplicate its work here.
2. Diff recent changes against documentation:
   ```powershell
   git log --oneline -20
   git diff --stat HEAD~5 2>$null
   ```
   Identify what actually changed: new/removed scripts, new modules, migration
   milestones, schema changes, new workstreams (e.g. a new AWS service being
   introduced).
3. For each README outside the Terraform-doc scope, compare its claims against
   the files/scripts it describes (file names, flags, commands, prerequisites,
   directory trees). Correct anything stale. Do not invent capability that
   doesn't exist in the code.
4. Update `PROGRESS.md`:
   - Update the "Last updated" date.
   - Update the relevant workstream section(s) only — move completed
     "Not started" items into "Done", add newly-scoped workstreams, and keep
     each section short (this is an index, not a log).
   - Never promote a proposal or in-progress decision to "Done." Match the
     confidence language already used in the referenced detailed docs
     (e.g. the Attio/PostgreSQL migration decision log, when working on that
     workstream).
5. Preserve hand-written rationale and section ordering unless it's actually
   wrong. Never delete a workstream section just because it's quiet — mark it
   accurately instead (e.g. "not started", "blocked on X").
6. Run, if Terraform or scripts changed:
   ```powershell
   terraform fmt -check -recursive
   git diff --check
   ```
7. Report what changed, or say explicitly that nothing needed updating.

## Source-of-truth rules

- Code, scripts, and Terraform are the source of truth — not this skill's
  memory of a previous session, and not chat history.
- For the Attio/PostgreSQL migration workstream specifically, defer to the
  detailed decision log referenced in `AGENTS.md` for field-level claims;
  `PROGRESS.md` only carries the coarse, already-confirmed summary.
- Never copy secrets, credentials, personal emails, or IP addresses into
  `PROGRESS.md` or any README.
- If unsure whether something is actually done vs. in progress, mark it as
  in progress and say why in the report — do not guess.
