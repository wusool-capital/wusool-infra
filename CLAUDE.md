# CLAUDE.md

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

## 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.
– The golden rule: ALWAYS consult your advisor before finalizing a plan.

## 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

## 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

## 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"
– Once the entire build process is succeeded, ask the user 'Ready for a full code-review?' -> if yes proceed to use /code-review
– Use standard commit prefixes (e.g., feat, fix, docs, chore).

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]

For implementation plans, always use the `concise-plan` skill; plans must be short, concrete, file-oriented, and Codex-style—never verbose or essay-like.

```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

## 5. Repo Standards (wusool-infra)

Concrete rules for this repository. They are enforced in CI — follow them
while writing, not after a failed pipeline.

### Type safety is not optional

- Pydantic v2 (`pydantic-settings`) for every `Settings` class and every
  I/O schema; frozen dataclasses for framework-free domain values (`Money`,
  entities, value objects).
- No bare `dict` / `list` / `Any` at a module or function boundary — model
  it. `ruff` ANN (annotation completeness) is on; annotate every signature.
- Ports are `typing.Protocol`s at the `application/` boundary and **never
  expose ORM types** — map to/from domain objects in `persistence/`.

### Run the checks before every commit and PR

From `server/` (any change under `server/**`):

```bash
uv run ruff check .
uv run ty check .
uv run pytest
uv run alembic check   # if models or migrations changed
```

From `infrastructure/terraform/` (any Terraform change): `tofu fmt -check
-recursive`, then `tofu init -backend=false && tofu validate` in each changed
stack. PowerShell changes: `Invoke-ScriptAnalyzer` (Warning + Error) clean.

### Structure

- `server/` modules are layered `domain → application → persistence →
  providers → api`. Dependencies point inward only. The per-module and
  repo-wide `tests/test_architecture.py` fitness tests enforce this — if you
  add a cross-layer or cross-module import, expect them to fail, and fix the
  design rather than the test.
- New peer module or a documented full-access exception → update the module
  `__all__` and its README, and state the exception explicitly.
- Before finalizing a PR that touches `server/**`, run the
  `/modular-monolith` skill and reconcile any layering or module-boundary
  drift it flags — the passing fitness tests are the floor, not the ceiling.

### Schema, config, secrets

- Schema changes go through an Alembic migration in `server/alembic/` with
  data-engineer sign-off. Never ad-hoc SQL, never runtime DDL, never a new
  flat SQL file.
- A new setting → add it to the module `Settings` **and**
  `server/.env.example` (`tests/test_env_example.py` fails otherwise).
- Secrets live only in AWS Secrets Manager. Never in `*.tfvars`, a committed
  `.env`, or code.
- CRM writes go to Attio first, then Postgres (see
  `server/app/modules/ddl_commands/README.md` for why).

### After the change

- Update the affected README, `CHANGELOG.md`, and the relevant `docs/` page
  in the same PR — run `$sync-terraform-docs` / `$sync-project-docs` /
  `$sync-crm-schema-docs` for the area you touched.
- Once the build passes, ask the user "Ready for a full code-review?" before
  running `/code-review`.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
