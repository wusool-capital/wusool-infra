-- One new, additive table for the Phase 3 Slack matching workflow's
-- run-audit / shortlist / status / approval needs. Does not alter, rename,
-- or drop any existing table or column. See
-- DOCS/migration/PHASE3_MATCH_RESULTS_HANDOVER.md for full rationale.

CREATE TABLE IF NOT EXISTS match_results (
    id                            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    run_id                        UUID NOT NULL,

    buyer_attio_id                TEXT NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
    buyer_role_id                 UUID NOT NULL REFERENCES buyer_roles(id) ON DELETE CASCADE,

    -- NULL on this row  => this is the run/header row (see handover doc).
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
