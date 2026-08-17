# Alembic + SQLAlchemy Migration — Handover

Phase G of `Final_restructure_plan.md`, explicitly deferred by request
("alembic can be done later") while Phases C/E/F/H1 and the CD restructure
landed. **Nothing in this document has been executed.** This is the plan as
scoped and decided, verified against the live codebase on 2026-08-17, for
whoever picks this up next (possibly a future me, with no memory of this
conversation).

## Why this isn't a small task

The original plan assumed Alembic would land *before* the ECR digest pivot
(Phase F). Phase F shipped first. That ordering change, plus two decisions
made explicitly during scoping, make this bigger than the original plan
priced it:

1. **Models physically relocate into a new `database/` package** (full
   relocation, not a smaller "just share one `Base`" move) — decided
   explicitly when asked, trading a larger diff for `database/` being
   unambiguously the only place any table is defined.
2. **`ddl-commands` points at the same `database/` package too** — its
   current `Organization` mapping (a deliberately narrow ~5-column subset)
   gets replaced by the richer one, a real behavior change for that app, not
   just an import path change.
3. Because Phase F already shipped, this now also requires rebuilding and
   redeploying the toolkit Docker image (widened build context) — a cost the
   original plan didn't have to pay.

## Current state, verified 2026-08-17

- **23 real tables** in `wusool_crm` (`database/sql/001_extensions.sql`
  through `008_bot_managed_columns.sql`). Confirmed by counting
  `^CREATE TABLE` lines directly — the plan's own "~22" was already wrong.
- **9 already mapped as SQLAlchemy models**, across two separate,
  independent `Base` instances:
  - `matching-engine/app/shared/database/models/`: `Organization`, `Person`,
    `Deal`, `Mandate`, `Meeting` (shared-kernel), plus `BuyerRole`
    (`app/modules/buyers/infrastructure/models.py`), `SellerRole`
    (`app/modules/sellers/infrastructure/models.py`), `MatchScore`/
    `MatchResult` (`app/modules/matching/infrastructure/models.py`).
  - `ddl-commands/ddl_commands/shared/database/models/`: its own separate
    `Base`, its own **narrower** `Organization` (only `name`, `hq_country`,
    `geographic_focus`, `sector_focus`, `relationship_status` — by design,
    "only the columns this bot actually reads/displays"), plus its own
    `BuyerRole`/`SellerRole` copies.
- **14 missing**: `users`, `investor_lender_roles`, `activities`,
  `deal_stage_events`, `signals`, `buyer_intel`, `seller_financials`,
  `mandate_targets`, `documents`, `vertical_kb`, `graph_edges`,
  `attio_sync_state`, `attio_raw_events`, `scorecards`.
- **Scribe** (meeting transcription, separate repo) already runs its own
  Alembic chain against this same database, writing `meetings` via the
  `scribe_pub` role. Not resolved — see "Scribe coordination" below.
- No `database/` Python package exists yet — today `database/` is docs +
  flat SQL + PowerShell scripts only, not a Python package of any kind.

## Decisions already made (don't re-litigate these)

| Question | Decision | Why |
|---|---|---|
| Where do models live? | New `database/` package becomes the real source of truth; `matching-engine` and `ddl-commands` import from it | Explicit choice over the cheaper "share one Base, leave files where they are" alternative |
| Move scope | **Full relocation** — all 23 models physically under `database/`, not just the 5 shared ones | Explicit choice over a smaller "Base-only move" alternative |
| ddl-commands' narrower `Organization` | Gets replaced by the richer one from `database/` | Explicit choice — "point this one as well to the main database folder" |
| Alembic `version_table` | Must be a **distinct name**, not the default `alembic_version` | Scribe's own chain already uses the default name against the same DB; whichever runs second would clobber the other's head revision |
| Baseline revision | `alembic stamp`, **never** `alembic upgrade` | Tables already exist in both dev and prod (prod's RDS was restored from a dev snapshot earlier this year, so it already carries the full schema — the original plan's "prod has no database today" is stale) |

## Blocking technical facts (verified, not assumptions)

1. **uv workspace members must live under the workspace root.**
   `workflows/wusool-toolkit/pyproject.toml`'s `[tool.uv.workspace]` is
   rooted there; `database/` is a sibling directory at the repo root, one
   level up. It **cannot** be a workspace member. Use a path dependency
   instead: in both `matching-engine/pyproject.toml` and
   `ddl-commands/pyproject.toml`, add
   `[tool.uv.sources] wusool-db = { path = "../../../database", editable = true }`
   (three `../` — from `workflows/wusool-toolkit/matching-engine/` up to
   repo root). Decide this before writing `database/pyproject.toml`, since
   it determines whether `database/` needs its own `[build-system]` at all
   (it does, for the path dependency to install cleanly).

2. **Merging Base means every mapped class must actually import into one
   metadata, or autogenerate proposes dropping the others.** `BuyerRole`,
   `SellerRole`, `MatchScore`, `MatchResult` currently live on
   matching-engine's own `Base` (via files under `app/modules/*/`), and
   ddl-commands has its own separate copies. Under full relocation, all of
   them move physically under `database/models/`; `matching-engine` and
   `ddl-commands` then import the *classes* from there instead of owning
   any model file. `env.py`'s `target_metadata` must import every model
   module — a missing import is a silent `DROP TABLE` in the next
   `--autogenerate`, not an error. Add a test asserting
   `len(Base.metadata.tables) == 23` once the count is final.

3. **~40 files need import-path rewrites**, not just the model files
   themselves. Grep confirmed these reference the old paths and will break:

   ```
   # matching-engine (app code + tests)
   app/shared/database/__init__.py
   app/modules/matching/infrastructure/{meeting_repository,repositories,models}.py
   app/modules/matching/application/{use_cases,mappers}.py
   app/modules/buyers/{infrastructure/{models,repositories},application/mappers}.py
   app/modules/sellers/{infrastructure/{models,repositories},application/mappers}.py
   tests/conftest.py
   tests/integration/test_{buyer_lookup,nullable_fields,schema_drift,
     match_score_repository,organizations,buyer_repository,
     match_orchestration_e2e,buyer_roles,seller_repository,seller_roles}.py

   # ddl-commands (app code + tests)
   ddl_commands/shared/database/__init__.py
   ddl_commands/modules/slack/views/{buyer_form,seller_form}.py
   ddl_commands/modules/buyers/{infrastructure/repositories,
     application/{resolution_service,use_cases},dependencies}.py
   ddl_commands/modules/sellers/{infrastructure/repositories,
     application/{resolution_service,use_cases},dependencies}.py
   tests/conftest.py
   tests/integration/test_{buyer_use_cases,buyer_repository,
     seller_use_cases,seller_repository}.py
   ```

   Run both test suites green (`uv run pytest` from each package's own
   directory — they have separate `testpaths`, see the `ci.yml` fix from
   the CD restructure for why running from the wrong directory silently
   skips a suite) before moving past this stage.

4. **`meeting.py`'s three ENUMs will break a from-empty `upgrade head`.**
   `_MeetingSource`/`_CounterpartyRole`/`_MeetingType` are all declared with
   `create_type=False` (correct for this app — it only ever reads
   `meetings`, never creates the schema). An `upgrade head` against an empty
   database will fail on the `meetings` revision because the types were
   never created. The hand-written revision that adds the pgvector/enum/role
   DDL (step 5 below) must `CREATE TYPE` before that revision runs. **Do
   not** flip any model to `create_type=True` to fix this — that breaks any
   test doing `metadata.create_all()` against a database that already has
   the types (integration tests do this today).

5. **Reflect the live database for the 14 missing tables' real columns —
   never the `.sql` files.** `008_bot_managed_columns.sql` is pure `ALTER
   TABLE`, and `004_machine_layer.sql` has conditional re-apply logic around
   a specific column (see its own comment, line ~155) — neither file is a
   clean "replay this and get today's schema" script. Connect via
   `database/rds-tunnel-runbook.md`'s SSM port-forward, then reflect with
   `sqlalchemy.inspect()` or `psql \d`, not by reading SQL source.

6. **Docker rebuild required this time.** Once `database/` becomes an
   installable dependency of `matching-engine`/`ddl-commands`, the
   Dockerfile's build context (currently scoped to
   `workflows/wusool-toolkit/`) must widen to include `database/` from the
   repo root, plus a `.dockerignore` so `.git/`, `terraform/`, and the other
   workflows don't balloon the image. This means: rebuild, push, new digest,
   update `envs/dev.tfvars`, apply, verify — the exact same closed-loop
   verification chain used for the original ECR digest pivot (SSM bootstrap
   polled to `Success`, `/health` returns 200, running container's digest
   confirmed to match what was pushed). Do this on dev only, deliberately,
   before touching prod's `image_digest`.

## Scribe coordination — must be answered before Phase G lands, not after

Two independent Alembic chains against one database corrupt each other's
`alembic_version` state unless coordinated. A distinct `version_table` name
(decision above) makes the two chains *not conflict mechanically*, but
doesn't answer who owns `meetings`' DDL. Three options, unchanged from the
original plan, still unresolved:

- **(a) wusool-infra owns all `wusool_crm` DDL** (recommended in the
  original plan). Scribe stops migrating `meetings`; its own chain is
  retired or scoped to tables this repo doesn't manage.
- **(b) Split by schema.** Scribe owns a dedicated Postgres schema
  end-to-end; wusool-infra owns `public`. Requires moving `meetings`.
- **(c) Scribe keeps `meetings`.** wusool-infra's `env.py` needs an
  `include_object` hook excluding `meetings` from autogenerate, and that
  exclusion must be commented in the file — the next `--autogenerate`
  without it proposes dropping a table this repo doesn't manage.

This is a conversation with whoever maintains the scribe repo, not a
decision to make unilaterally from this repo. `SCRIBE_INFRA_CONTRACT.md`
(§11) already flags this same three-way choice from scribe's side — read
both together.

## Staged execution plan

Each stage is its own commit, verified before moving to the next — same
discipline as the CD restructure. Advisor review recommended before starting
stage 2 (the point of no easy rollback, since it touches the live Docker
image) and again before stage 4 (the point of no easy rollback for the
database itself).

1. **Package skeleton + full relocation + import rewrite.**
   `database/wusool_db/` (or similar — name not yet decided) owns all 23
   models. Update both `pyproject.toml`s with the path dependency. Rewrite
   the ~40 import sites. Both test suites green, run from their own
   directories. No live database or Docker changes yet.

2. **Docker rebuild + redeploy (dev only).** `.dockerignore`, widen build
   context, rebuild, push, new digest, `envs/dev.tfvars`, apply, verify —
   full closed-loop chain, not just a green `tofu apply`.

3. **Alembic scaffold.** `database/alembic.ini` + `migrations/env.py`, with
   a distinct `version_table` set in **both** the online and offline
   branches of `env.py` (easy to set only one and have it silently not
   apply depending on how the CI job invokes it), plus the `include_object`
   hook if Scribe coordination lands on option (c). No revisions yet.

4. **Baseline revision.** Autogenerate `0001` against a **live dev
   reflection** (not the `.sql` files — see point 5 above), then
   `alembic stamp head` on dev. Then the same `stamp` (not `upgrade`) on
   prod, since its snapshot-restored RDS already carries the schema. Verify
   `alembic check` reports no drift immediately after stamping either
   environment.

5. **Hand-written revisions** for what reflection can't see: the pgvector
   extension guard, the three enum `CREATE TYPE` statements (before the
   revision that reaches `meetings`), the `scribe_pub` role + its `GRANT`s,
   the trigram GIN index on `organizations.name`. Keep
   `database/sql/00*.sql` until this step's `alembic upgrade head` on a
   throwaway empty database produces a schema `database/validate-postgres.ps1`
   or a SQLAlchemy-side schema-diff reports as identical to live dev — only
   then consider deleting the flat SQL files, and only in a follow-up, not
   as part of this stage.

6. **CI.** Extend `ci.yml` with `alembic upgrade head` against a throwaway
   Postgres service container, then `alembic check` for drift. This is the
   first point a future PR gets automatic feedback if a new model isn't
   wired into `target_metadata` correctly.

## What this explicitly does not include

- **H2** (migrating n8n's own data off the instance and onto the shared
  Postgres) — separate, still deferred.
- **H3** (a recurring backup policy for the RDS instances) — separate, still
  deferred.
- Any decision on the scribe coordination question above — that's a
  cross-repo conversation, not something to resolve unilaterally while
  executing this plan.
