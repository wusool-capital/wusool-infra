CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- Trigram similarity — fuzzy/typo-tolerant organization-name search
-- (matching-engine's BuyerRepository.search_by_organization_name).
CREATE EXTENSION IF NOT EXISTS pg_trgm;

DO $$
BEGIN
  CREATE EXTENSION IF NOT EXISTS vector;
EXCEPTION
  WHEN undefined_file THEN
    RAISE NOTICE 'pgvector extension is not installed on this PostgreSQL server; vector columns will be created after pgvector is available.';
END
$$;
