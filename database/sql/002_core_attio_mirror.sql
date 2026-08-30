CREATE TABLE IF NOT EXISTS users (
  attio_id text PRIMARY KEY,
  name text NOT NULL,
  email text,
  access text,
  active boolean NOT NULL DEFAULT true,
  raw_attio jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS organizations (
  attio_id text PRIMARY KEY,
  name text NOT NULL,
  description text,
  type text[] NOT NULL DEFAULT '{}',
  client_type text,
  sector_focus text[] NOT NULL DEFAULT '{}',
  stage_focus text[] NOT NULL DEFAULT '{}',
  geographic_focus text[] NOT NULL DEFAULT '{}',
  hq_country text,
  domains text[] NOT NULL DEFAULT '{}',
  categories text[] NOT NULL DEFAULT '{}',
  relationship_status text,
  connection_strength text,
  owner_attio_id text REFERENCES users(attio_id),
  last_interaction_at timestamptz,
  funding_raised jsonb,
  estimated_arr text,
  removed_at timestamptz,
  raw_attio jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- Compatibility for a pre-#73 flat-SQL database. Rename the populated table
-- in place before CREATE TABLE IF NOT EXISTS can create an empty sibling.
DO $$
BEGIN
  IF to_regclass('public.people') IS NOT NULL
     AND to_regclass('public.person') IS NULL THEN
    ALTER TABLE people RENAME TO person;
  ELSIF to_regclass('public.people') IS NOT NULL
        AND to_regclass('public.person') IS NOT NULL THEN
    RAISE EXCEPTION 'Both people and person exist; refusing to split person data across two tables.';
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS person (
  attio_id text PRIMARY KEY,
  name text NOT NULL,
  role text,
  company_attio_id text REFERENCES organizations(attio_id),
  email text[] NOT NULL DEFAULT '{}',
  linkedin text,
  relationship_status text,
  connection_strength text,
  owner_attio_id text REFERENCES users(attio_id),
  past_employers jsonb NOT NULL DEFAULT '[]'::jsonb,
  education jsonb NOT NULL DEFAULT '[]'::jsonb,
  enrichment jsonb NOT NULL DEFAULT '{}'::jsonb,
  last_interaction_at timestamptz,
  job_title text,
  contact_type text,
  phone text,
  avatar_url text,
  angellist text,
  facebook text,
  instagram text,
  twitter text,
  twitter_follower_count integer,
  removed_at timestamptz,
  raw_attio jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

-- CREATE TABLE IF NOT EXISTS does not add columns to a legacy table renamed
-- above. Keep the Person contract required by sync-postgres.ps1 complete.
ALTER TABLE person
  ADD COLUMN IF NOT EXISTS job_title text,
  ADD COLUMN IF NOT EXISTS contact_type text,
  ADD COLUMN IF NOT EXISTS phone text,
  ADD COLUMN IF NOT EXISTS avatar_url text,
  ADD COLUMN IF NOT EXISTS angellist text,
  ADD COLUMN IF NOT EXISTS facebook text,
  ADD COLUMN IF NOT EXISTS instagram text,
  ADD COLUMN IF NOT EXISTS twitter text,
  ADD COLUMN IF NOT EXISTS twitter_follower_count integer,
  ADD COLUMN IF NOT EXISTS removed_at timestamptz;

-- PostgreSQL keeps constraint/index names when their table is renamed. Align
-- the legacy names with migration 2f4edfbfb647, guarded for repeat runs.
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'person'::regclass AND conname = 'people_pkey')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'person'::regclass AND conname = 'person_pkey') THEN
    ALTER TABLE person RENAME CONSTRAINT people_pkey TO person_pkey;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'person'::regclass AND conname = 'people_company_attio_id_fkey')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'person'::regclass AND conname = 'person_company_attio_id_fkey') THEN
    ALTER TABLE person RENAME CONSTRAINT people_company_attio_id_fkey TO person_company_attio_id_fkey;
  END IF;
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'person'::regclass AND conname = 'people_owner_attio_id_fkey')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid = 'person'::regclass AND conname = 'person_owner_attio_id_fkey') THEN
    ALTER TABLE person RENAME CONSTRAINT people_owner_attio_id_fkey TO person_owner_attio_id_fkey;
  END IF;
  IF to_regclass('public.idx_people_company') IS NOT NULL
     AND to_regclass('public.idx_person_company') IS NULL THEN
    ALTER INDEX idx_people_company RENAME TO idx_person_company;
  END IF;
  IF to_regclass('public.idx_people_email') IS NOT NULL
     AND to_regclass('public.idx_person_email') IS NULL THEN
    ALTER INDEX idx_people_email RENAME TO idx_person_email;
  END IF;
  IF to_regclass('public.idx_graph_edges_people') IS NOT NULL
     AND to_regclass('public.idx_graph_edges_person') IS NULL THEN
    ALTER INDEX idx_graph_edges_people RENAME TO idx_graph_edges_person;
  END IF;
END
$$;

CREATE TABLE IF NOT EXISTS deals (
  attio_id text PRIMARY KEY,
  name text NOT NULL,
  stage text,
  stage_changed_at timestamptz,
  buyer_organization_attio_id text REFERENCES organizations(attio_id),
  buyer_person_attio_id text REFERENCES person(attio_id),
  seller_organization_attio_id text REFERENCES organizations(attio_id),
  owner_attio_id text REFERENCES users(attio_id),
  value jsonb,
  teaser_status text,
  nda_count integer NOT NULL DEFAULT 0,
  cim_ready boolean,
  deal_memo_ready boolean,
  contract_signed_date date,
  exclusivity_date date,
  next_task text,
  data_room_substatus text,
  comparables jsonb NOT NULL DEFAULT '{}'::jsonb,
  raw_attio jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT deals_one_buyer CHECK (
    buyer_organization_attio_id IS NULL OR buyer_person_attio_id IS NULL
  )
);

CREATE TABLE IF NOT EXISTS mandates (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  attio_id text UNIQUE,
  side text NOT NULL,
  buyer_attio_id text REFERENCES organizations(attio_id),
  seller_attio_id text REFERENCES organizations(attio_id),
  phase text,
  assigned_advisor_attio_ids text[] NOT NULL DEFAULT '{}',
  start_date date,
  expiry_date date,
  universe_constructed boolean NOT NULL DEFAULT false,
  shortlist_approved boolean NOT NULL DEFAULT false,
  universe_size integer,
  shortlist_size integer,
  tier1_contacted integer,
  responses integer,
  raw_attio jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);
