#!/usr/bin/env bash
set -euo pipefail

db_container=${1:?usage: verify_flat_sql_onboarding.sh <postgres-container-id>}
: "${DATABASE_URL:?DATABASE_URL must point at the test database}"

reset_schema() {
  docker exec -i "$db_container" psql -v ON_ERROR_STOP=1 -U matching -d wusool_crm <<'SQL'
DROP SCHEMA public CASCADE;
CREATE SCHEMA public;
GRANT ALL ON SCHEMA public TO public;
SQL
}

apply_flat_sql() {
  for sql_file in sql/*.sql; do
    docker exec -i "$db_container" psql -v ON_ERROR_STOP=1 -U matching -d wusool_crm \
      < "$sql_file" >/dev/null
  done
}

assert_person_contract() {
  docker exec -i "$db_container" psql -v ON_ERROR_STOP=1 -U matching -d wusool_crm <<'SQL'
DO $$
DECLARE
  missing_columns text[];
  person_fk_count integer;
BEGIN
  IF to_regclass('public.person') IS NULL OR to_regclass('public.people') IS NOT NULL THEN
    RAISE EXCEPTION 'expected only public.person to exist';
  END IF;

  SELECT array_agg(required.column_name ORDER BY required.column_name)
    INTO missing_columns
  FROM unnest(ARRAY[
    'job_title', 'contact_type', 'phone', 'avatar_url', 'angellist',
    'facebook', 'instagram', 'twitter', 'twitter_follower_count', 'removed_at'
  ]) AS required(column_name)
  WHERE NOT EXISTS (
    SELECT 1
    FROM information_schema.columns actual
    WHERE actual.table_schema = 'public'
      AND actual.table_name = 'person'
      AND actual.column_name = required.column_name
  );

  IF missing_columns IS NOT NULL THEN
    RAISE EXCEPTION 'person is missing columns: %', missing_columns;
  END IF;

  SELECT count(*) INTO person_fk_count
  FROM pg_constraint
  WHERE confrelid = 'person'::regclass
    AND conrelid IN ('deals'::regclass, 'buyer_roles'::regclass, 'graph_edges'::regclass);

  IF person_fk_count <> 4 THEN
    RAISE EXCEPTION 'expected 4 dependent FKs to target person, found %', person_fk_count;
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'person'::regclass
      AND conname IN (
        'people_pkey', 'people_company_attio_id_fkey', 'people_owner_attio_id_fkey'
      )
  ) OR to_regclass('public.idx_people_company') IS NOT NULL
    OR to_regclass('public.idx_people_email') IS NOT NULL
    OR to_regclass('public.idx_graph_edges_people') IS NOT NULL THEN
    RAISE EXCEPTION 'legacy people constraint or index names remain';
  END IF;
END
$$;
SQL
}

# A fresh legacy bootstrap must expose the complete Person contract used by
# sync-postgres.ps1, even before Alembic finishes the rest of the upgrade.
reset_schema
apply_flat_sql
assert_person_contract

# Re-running the bootstrap against a pre-rename snapshot must rename the
# populated table in place, never create an empty person beside people.
docker exec -i "$db_container" psql -v ON_ERROR_STOP=1 -U matching -d wusool_crm <<'SQL'
INSERT INTO person (attio_id, name) VALUES ('preserved-person', 'Preserved');
ALTER TABLE person RENAME TO people;
ALTER TABLE people RENAME CONSTRAINT person_pkey TO people_pkey;
ALTER TABLE people RENAME CONSTRAINT person_company_attio_id_fkey TO people_company_attio_id_fkey;
ALTER TABLE people RENAME CONSTRAINT person_owner_attio_id_fkey TO people_owner_attio_id_fkey;
ALTER INDEX idx_person_company RENAME TO idx_people_company;
ALTER INDEX idx_person_email RENAME TO idx_people_email;
ALTER INDEX idx_graph_edges_person RENAME TO idx_graph_edges_people;
SQL
apply_flat_sql
assert_person_contract
docker exec "$db_container" psql -v ON_ERROR_STOP=1 -U matching -d wusool_crm -Atc \
  "SELECT count(*) FROM person WHERE attio_id = 'preserved-person'" | grep -qx '1'

# The documented onboarding sequence must remain executable and land at the
# same schema as a clean Alembic install.
reset_schema
apply_flat_sql
uv run alembic stamp 87320bb9dc8d
uv run alembic upgrade head
uv run alembic check
