-- ===========================================================================
-- docs/wusool_meetings.sql
--
-- Canonical DDL for the meetings table in Wusool Capital's main database.
--
-- Scribe runs standalone with its own Postgres, so scribe's Alembic chain has
-- no connection to this database and therefore does NOT own this DDL — the
-- Wusool side runs this file. Scribe only ever INSERTs/UPDATEs the table.
--
-- This file is applied verbatim by tests/integration/publish/test_publish_service.py,
-- so it is verified against the code that writes to it rather than drifting
-- from it. Change the column set here and the publish tests will tell you.
--
-- See docs/wusool_publish.md for the surrounding runbook (grants, networking,
-- config) and app/publish/service.py for the field-by-field mapping.
-- ===========================================================================

-- One row per conversation. source distinguishes producers: scribe always
-- writes 'in_house'; 'granola' and 'manual' are reserved for other paths.
CREATE TYPE meeting_source AS ENUM ('in_house', 'granola', 'manual');

-- Which side the counterparty sits on. A meeting may be tagged with both a
-- buyer and a seller in scribe; this column holds the primary one (seller
-- wins) and the other side is preserved in metadata->'other_side'.
CREATE TYPE counterparty_role AS ENUM ('buyer', 'seller');

CREATE TYPE meeting_type AS ENUM (
    'enrichment',
    'alignment',
    'owner_iv',
    'buyer_intro',
    'internal'
);

CREATE TABLE meetings (
    id                 uuid PRIMARY KEY,

    -- Attio Organization record id. Hard FK to organizations(attio_id) —
    -- see fk_meetings_org below.
    org_id             text,
    -- Set only when org_id could not be resolved, so the row is still
    -- useful and backfillable. Never both.
    org_name_raw       text,

    counterparty_role  counterparty_role,
    -- No source of truth in scribe yet (no Slack flag, no UI), so scribe
    -- writes NULL rather than guessing.
    meeting_type       meeting_type,

    occurred_at        timestamptz NOT NULL,
    title              text,
    source             meeting_source NOT NULL DEFAULT 'in_house',

    audio_ref          text,           -- s3://bucket/key, or a bare path for local storage
    duration_s         integer,

    -- Slack user id. Scribe has no user accounts (docs/security.md: "v1
    -- intentionally has no user roles"), so this is NULL today.
    created_by_ref     text,
    -- NULL today: scribe's diarization is a silence-gap heuristic that does
    -- not identify who is speaking, so publishing its placeholder labels
    -- would put fabricated identities in this table.
    participants       jsonb,

    transcript         text,           -- full transcript, inlined from S3
    summary            text,           -- rendered from the structured AI summary
    metadata           jsonb NOT NULL DEFAULT '{}',

    created_at         timestamptz NOT NULL DEFAULT now(),

    -- Back-pointer to scribe.meetings.id. LOAD-BEARING: the publish job is
    -- retried on failure, and this unique constraint is what makes the
    -- upsert idempotent instead of producing duplicate rows.
    scribe_meeting_id  uuid UNIQUE
);

CREATE INDEX ix_meetings_org_id      ON meetings (org_id);
CREATE INDEX ix_meetings_occurred_at ON meetings (occurred_at);

-- ---------------------------------------------------------------------------
-- Real referential integrity to Organization. Enabled 2026-08-11: publish
-- now checks organization existence before insert, so the sync-lag race
-- this was originally soft-referenced against is no longer expected.
--
-- If scribe's publish job starts failing on this FK, that assumption was
-- wrong — revert with:
--   ALTER TABLE meetings DROP CONSTRAINT fk_meetings_org;
-- ---------------------------------------------------------------------------

ALTER TABLE meetings
    ADD CONSTRAINT fk_meetings_org
    FOREIGN KEY (org_id) REFERENCES organizations (attio_id);

-- ---------------------------------------------------------------------------
-- Least-privilege role for scribe. Scribe needs nothing beyond writing this
-- one table and reading Organization to resolve names to Attio ids.
--
-- CREATE ROLE scribe_pub LOGIN PASSWORD '<generate-a-strong-one>';
-- GRANT SELECT, INSERT, UPDATE ON meetings     TO scribe_pub;
-- GRANT SELECT                 ON organizations TO scribe_pub;
-- ---------------------------------------------------------------------------

-- ---------------------------------------------------------------------------
-- Optional: embedding column for M5 recall.
--
-- Scribe does NOT write this — it generates no embeddings, and its local
-- Postgres image has no pgvector, so creating it from scribe's side would
-- break local migrations. Add it when the embedding pipeline exists:
--
-- CREATE EXTENSION IF NOT EXISTS vector;
-- ALTER TABLE meetings ADD COLUMN summary_embedding vector(1536);
-- ---------------------------------------------------------------------------
