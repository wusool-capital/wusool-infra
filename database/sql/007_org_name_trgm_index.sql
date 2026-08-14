-- GIN trigram index for fuzzy/typo-tolerant organization-name search
-- (matching-engine's BuyerRepository.search_by_organization_name). Requires
-- pg_trgm, enabled in 001_extensions.sql.
CREATE INDEX IF NOT EXISTS ix_organizations_name_trgm
    ON organizations USING gin (name gin_trgm_ops);
