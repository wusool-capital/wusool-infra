# Handover: `match_results` table (Phase 3 matching backend)

**For:** the DB team
**Action needed:** create one new, additive table in `wusool_crm`. No existing
table is altered, renamed, or dropped.
**Not yet applied:** this table does not exist in `wusool_crm` today. The
matching-engine backend's Phase 3 Slack workflow (approve/reject, match
status, run audit) cannot persist anything until this is created.

See also:

- [Client schema overview](CLIENT_SCHEMA_OVERVIEW.md) — the real, currently
  deployed schema this table sits alongside.
- `matching-engine/README.md` — the application's own account of this same
  gap.

## Why this table exists

The matching-engine backend (`matching-engine/`) was scaffolded against the
real, already-deployed `wusool_crm` schema (`database/sql/001-005*.sql`).
That schema has `buyer_roles`, `seller_roles`, and a single `match_scores`
table (one row per scored buyer/seller pair — score, a JSONB scoring
breakdown, an LLM reasoning narrative, JSONB citations). It does **not**
have `match_runs`, `matches`, `match_evidence`, or `approvals` — tables a
separate product-requirements document (`PRD.md`, this repo's root) describes
as intended, but which were never actually built.

Phase 3 connects the backend to Slack for a real `/find-match` product loop,
which needs to durably persist:

- **Run audit** — did the run succeed, how many candidates were considered/
  filtered, what happened if it failed, when did it start/finish.
- **Match status** — `GENERATED → PENDING_REVIEW → APPROVED/REJECTED`, enforced
  by the application as an explicit state machine, not just a DB `CHECK`.
- **Approval decisions** — who approved/rejected a match and when, via Slack.
- **The shortlisted results themselves** — rank, score, confidence, and the
  LLM's narrative (why it matches, why it was chosen over alternatives,
  pitch, risks) for each of the top-N candidates surfaced to a buyer.

None of that has anywhere to live in the current schema. Rather than inventing
several new tables to mirror `PRD.md`'s aspirational design one-for-one, this
is **one** table sized to cover all of the above, reusing `match_scores`
as-is for the deterministic scoring breakdown it already owns.

## Design: one row-kind invariant, two row shapes

Four of the most important failure modes (extraction failure, candidate
retrieval failure, scoring failure, reasoning failure) happen *before any
candidate is chosen* — and the run still needs to be queryable and
diagnosable when that happens. So instead of a separate "run" table plus a
separate "candidate" table, `match_results` holds both, distinguished by
whether `rank` is set:

- **Exactly one row per `run_id` has `rank IS NULL`.** This is the **run
  row** — the audit record for the whole `/find-match` invocation. Only this
  row's run-level columns are meaningful (`requested_by`, `model_version`,
  `requirement_profile_version`, `requirement_profile`, `candidates_considered`,
  `candidates_filtered`, `filters_skipped`, `final_candidate_ids`,
  `execution_duration_ms`, `errors`, `started_at`, `completed_at`). It's
  created at the very start of a run (before extraction/scoring/reasoning
  even begin) so the run stays queryable no matter where it fails, and it's
  updated exactly once, at the end, with a single `UPDATE`.
- **Rows with `rank IS NOT NULL`** are **candidate rows** — one per
  shortlisted candidate (1..`STAGE3_TOP_N`, so at most a handful per run).
  Each links back to the existing `match_scores` row for that buyer/seller
  pair (`match_score_id`) for the deterministic criterion-level breakdown,
  and carries its own status/approval/narrative fields.

A partial unique index (`WHERE rank IS NULL`) enforces "exactly one run row
per run" at the database level, so this invariant can't silently drift.

## DDL

Purely additive — `CREATE TABLE IF NOT EXISTS`, matching the exact guarded
style already used in `database/sql/002-004` (`005` skipped the guard;
this shouldn't repeat that). Safe to re-run. Applied as
`database/sql/006_match_results.sql`. (`organizations.funding_raised`/
`estimated_arr` were folded directly into `002_core_attio_mirror.sql`'s
original `CREATE TABLE organizations` instead of getting their own file,
so this slot was free.)

```sql
-- database/sql/006_match_results.sql
--
-- One new, additive table for the Phase 3 Slack matching workflow's
-- run-audit / shortlist / status / approval needs. Does not alter, rename,
-- or drop any existing table or column. See
-- workflows/crm-sync/docs/PHASE3_MATCH_RESULTS_HANDOVER.md for full rationale.

CREATE TABLE IF NOT EXISTS match_results (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                        UUID NOT NULL,

    buyer_attio_id                TEXT NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
    buyer_role_id                 UUID NOT NULL REFERENCES buyer_roles(id) ON DELETE CASCADE,

    -- NULL on this row  => this is the run/header row (see design note above).
    -- NOT NULL           => this is a shortlisted candidate row (1..STAGE3_TOP_N).
    rank                          INTEGER,

    -- Candidate-row-only columns (NULL on the run row):
    seller_attio_id               TEXT REFERENCES organizations(attio_id) ON DELETE CASCADE,
    seller_role_id                UUID REFERENCES seller_roles(id) ON DELETE CASCADE,
    match_score_id                UUID REFERENCES match_scores(id),
    match_score                   NUMERIC,
    data_confidence               NUMERIC,
    why_chosen_over_alternatives  TEXT,
    recommended_pitch             TEXT,
    risks_and_gaps                TEXT,
    status                        TEXT NOT NULL DEFAULT 'GENERATED'
                                   CHECK (status IN ('GENERATED', 'PENDING_REVIEW', 'APPROVED', 'REJECTED', 'FAILED')),
    approved_by                   TEXT,
    decision                      TEXT CHECK (decision IN ('APPROVED', 'REJECTED')),
    decided_at                    TIMESTAMPTZ,
    decision_notes                TEXT,

    -- Run-row-only columns (NULL on candidate rows):
    requested_by                  TEXT,
    model_version                 TEXT,
    requirement_profile_version   INTEGER,
    requirement_profile           JSONB,
    candidates_considered         INTEGER,
    candidates_filtered           INTEGER,
    filters_skipped                JSONB NOT NULL DEFAULT '[]',
    vector_queries                 JSONB,
    final_candidate_ids             JSONB,
    execution_duration_ms            INTEGER,
    errors                             JSONB,
    started_at                        TIMESTAMPTZ NOT NULL DEFAULT now(),
    completed_at                       TIMESTAMPTZ,

    -- Unstructured future-proofing column. Not read or written by the
    -- application in this phase; reserved so a later phase or a DB-team
    -- backfill has room without a second migration.
    metadata                          JSONB NOT NULL DEFAULT '{}',

    created_at                        TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Enforces "exactly one run/header row per run_id" at the DB level.
CREATE UNIQUE INDEX IF NOT EXISTS uq_match_results_run_header
    ON match_results (run_id) WHERE rank IS NULL;

CREATE INDEX IF NOT EXISTS idx_match_results_run_id ON match_results(run_id);
CREATE INDEX IF NOT EXISTS idx_match_results_buyer_role ON match_results(buyer_role_id);
CREATE INDEX IF NOT EXISTS idx_match_results_status ON match_results(status);
```

## Column notes

| Column | Why |
| --- | --- |
| `run_id` | Groups one run row + its candidate rows together. Not the primary key — `id` is — so each row is still independently addressable (e.g. a single candidate row by its own `id` for an Approve/Reject action). |
| `rank` | The row-kind discriminator. `NULL` = run row, `1..N` = candidate row. See design note. |
| `status` | Includes `FAILED` in addition to the four values `PRD.md` describes (`GENERATED`/`PENDING_REVIEW`/`APPROVED`/`REJECTED`) — a run or candidate that fails needs a terminal, queryable state; nothing in the current schema provides one. |
| `match_score_id` | Links a candidate row back to the existing `match_scores` row for that buyer/seller pair — the deterministic per-criterion breakdown stays in `match_scores`, exactly where Phase 2 already put it. This table does not duplicate that breakdown. |
| `requirement_profile` / `requirement_profile_version` | There's no `buyer_requirement_profiles` table (flat `buyer_roles` has no version column). The extracted requirement profile is stored directly on the run row instead; version is only assigned on a *successful* extraction — a run that fails before/at extraction leaves both `NULL` rather than burning or colliding with a version number. |
| `filters_skipped`, `final_candidate_ids`, `errors` | JSONB, matching the shape `PRD.md`'s `match_runs.filters_skipped`/`.errors` already describe — free-form and forward-compatible rather than a rigid schema. |
| `vector_queries` | Present for shape-compatibility with `PRD.md`'s intended `match_runs` table. Branch 1 does not do vector/semantic retrieval, so this stays `NULL` — never populated with placeholder data. |
| `metadata` | Requested as a deliberate, unused-for-now extension point (see DDL comment). |

## What does *not* need a new table

- **Evidence** (`PRD.md`'s `match_evidence`) — reuses the *already-existing*
  `match_scores.citations` JSONB column. No new table.
- **Versioned requirement profiles** — folded into this table's
  `requirement_profile`/`requirement_profile_version`, as above.

One table covers everything Phase 3's persistence needs.

## How to apply

Same flow as `001-005` — see `database/README.md`:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass `
  -File .\database\setup-postgres.ps1
```

`setup-postgres.ps1` picks up `database/sql/*.sql` in filename order, so
`006_match_results.sql` runs after `001-005` automatically once the file is
in place. It uses `CREATE ... IF NOT EXISTS`, so re-running it is safe.

This session has no access to the real RDS instance (confirmed during Phase
2's database-integration work — the available AWS credentials belong to an
unrelated, empty account), so this migration has **not** been applied by this
session. Until the DB team runs it, the matching-engine backend's Phase 3
database-integration tests will skip cleanly (same pattern as the rest of
`tests/integration/`) rather than fail, and the app will report the missing
table plainly if something tries to use it.
