CREATE TABLE IF NOT EXISTS activities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  subject_type text NOT NULL,
  subject_attio_id text,
  subject_uuid uuid,
  actor_attio_id text REFERENCES users(attio_id),
  ts timestamptz NOT NULL DEFAULT now(),
  channel text,
  direction text,
  outcome text,
  source text,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT activities_subject_present CHECK (
    subject_attio_id IS NOT NULL OR subject_uuid IS NOT NULL
  )
);

CREATE TABLE IF NOT EXISTS deal_stage_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_attio_id text NOT NULL REFERENCES deals(attio_id) ON DELETE CASCADE,
  from_stage text,
  to_stage text NOT NULL,
  ts timestamptz NOT NULL DEFAULT now(),
  source text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS signals (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_attio_id text NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
  source text NOT NULL,
  payload jsonb NOT NULL DEFAULT '{}'::jsonb,
  ts timestamptz NOT NULL DEFAULT now(),
  rank integer,
  source_cite text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS buyer_intel (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_attio_id text NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
  cash_window jsonb NOT NULL DEFAULT '{}'::jsonb,
  appetite_score numeric,
  brief text,
  ideal_target jsonb NOT NULL DEFAULT '{}'::jsonb,
  generated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS seller_financials (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  seller_attio_id text NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
  normalised_ebitda_sde jsonb NOT NULL DEFAULT '{}'::jsonb,
  add_backs jsonb NOT NULL DEFAULT '[]'::jsonb,
  proxy_revenue jsonb NOT NULL DEFAULT '{}'::jsonb,
  confidence numeric,
  source_cite jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS mandate_targets (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  mandate_id uuid NOT NULL REFERENCES mandates(id) ON DELETE CASCADE,
  seller_attio_id text NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
  proxy_size jsonb NOT NULL DEFAULT '{}'::jsonb,
  tier text,
  score numeric,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (mandate_id, seller_attio_id)
);

CREATE TABLE IF NOT EXISTS match_scores (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  buyer_attio_id text NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
  seller_attio_id text NOT NULL REFERENCES organizations(attio_id) ON DELETE CASCADE,
  score numeric NOT NULL,
  dims jsonb NOT NULL DEFAULT '{}'::jsonb,
  reasoning text,
  citations jsonb NOT NULL DEFAULT '[]'::jsonb,
  generated_at timestamptz NOT NULL DEFAULT now(),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS documents (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  deal_attio_id text NOT NULL REFERENCES deals(attio_id) ON DELETE CASCADE,
  kind text NOT NULL,
  output_type text,
  drive_ref text,
  extracted_json jsonb NOT NULL DEFAULT '{}'::jsonb,
  qc_state text,
  version integer NOT NULL DEFAULT 1,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS vertical_kb (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  sector text NOT NULL,
  tier1_research jsonb NOT NULL DEFAULT '{}'::jsonb,
  source_cite jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS graph_edges (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  person_a_attio_id text NOT NULL REFERENCES people(attio_id) ON DELETE CASCADE,
  person_b_attio_id text NOT NULL REFERENCES people(attio_id) ON DELETE CASCADE,
  hop text NOT NULL,
  basis text,
  source_cite jsonb NOT NULL DEFAULT '[]'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT graph_edges_not_self CHECK (person_a_attio_id <> person_b_attio_id)
);

CREATE TABLE IF NOT EXISTS attio_sync_state (
  sync_name text PRIMARY KEY,
  last_cursor text,
  last_synced_at timestamptz,
  metadata jsonb NOT NULL DEFAULT '{}'::jsonb,
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS attio_raw_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  idempotency_key text UNIQUE,
  event_type text NOT NULL,
  payload jsonb NOT NULL,
  received_at timestamptz NOT NULL DEFAULT now(),
  processed_at timestamptz
);

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'vector') THEN
    ALTER TABLE buyer_intel
      ADD COLUMN IF NOT EXISTS brief_embedding vector(1536);
    ALTER TABLE vertical_kb
      ADD COLUMN IF NOT EXISTS embedding vector(1536);
  END IF;
END
$$;
