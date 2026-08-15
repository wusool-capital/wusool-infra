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

CREATE TABLE IF NOT EXISTS people (
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
  raw_attio jsonb NOT NULL DEFAULT '{}'::jsonb,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS deals (
  attio_id text PRIMARY KEY,
  name text NOT NULL,
  stage text,
  stage_changed_at timestamptz,
  buyer_organization_attio_id text REFERENCES organizations(attio_id),
  buyer_person_attio_id text REFERENCES people(attio_id),
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
