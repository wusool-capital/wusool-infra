# CRM Database Migration Brief

## Current Status

- Dev RDS PostgreSQL has been created privately inside the dev VPC.
- Database name is `wusool_crm`.
- Existing n8n EC2 remains the private access path for migrations and automation.
- Reusable SQL migrations have been created and run successfully.
- The schema contains 20 tables based on `Database_Architecture_ER_Diagram.drawio`.

## Architecture

```text
Attio = CRM system of record
PostgreSQL = machine / automation / intelligence layer
Join key = attio_id
```

Attio owns business-facing CRM state: companies, people, deals, buyer/seller
lists, owners, and pipeline state. PostgreSQL stores history, automation,
documents, extracted JSON, embeddings, buyer signals, match scores, graph edges,
and sync state.

## Terraform Changes

- `modules/postgres-rds/` defines the reusable private RDS PostgreSQL module.
- `modules/network/` now supports a second private subnet for DB subnet groups.
- `environments/dev/main.tf` wires PostgreSQL into the dev environment.
- `environments/dev/outputs.tf` exposes endpoint, DB name, SG, and secret ARN.

RDS is configured as private, encrypted, backed up, and deletion protected.

## Migration Scripts

SQL migrations live in `scripts/db/migrations/`:

| File | Purpose |
| --- | --- |
| `001_extensions.sql` | Enables `pgcrypto` and attempts `pgvector`. |
| `002_core_attio_mirror.sql` | Creates users, organizations, people, deals, and mandates. |
| `003_crm_roles.sql` | Creates buyer, seller, and investor/lender role tables. |
| `004_machine_layer.sql` | Creates activities, signals, documents, match scores, graph edges, and sync tables. |
| `005_indexes.sql` | Adds lookup and relationship indexes. |

Runner scripts:

- `scripts/db/migrate.ps1`
- `scripts/db/validate.ps1`

## Attio Migration Plan

Two migrations are required:

1. Source Attio to DEV Attio.
2. DEV Attio to PostgreSQL.

The first reusable step is read-only discovery:

- `scripts/attio/discover-attio.ps1`
- `scripts/attio/config/field-mapping.example.json`

Once source and DEV API tokens are available, discovery outputs real object and
list metadata under `outputs/attio/`. Those files drive field mapping and
idempotent migration scripts.
