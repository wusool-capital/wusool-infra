# Wusool CRM Database Migrations

These migrations implement the PostgreSQL machine layer from
`Database_Architecture_ER_Diagram.drawio`.

Attio remains the CRM system of record. PostgreSQL stores the reusable
automation and intelligence layer: activity history, documents, extracted JSON,
buyer signals, normalized seller financials, matching scores, graph edges,
stage history, and sync state. The durable join key is `attio_id`.

## Run

Set a PostgreSQL connection string and run the migrations:

```powershell
$env:DATABASE_URL = "postgresql://wusool_admin:password@host:5432/wusool_crm?sslmode=require"
.\scripts\db\migrate.ps1
.\scripts\db\validate.ps1
```

The scripts are idempotent for the current baseline: they use `CREATE TABLE IF
NOT EXISTS`, `CREATE INDEX IF NOT EXISTS`, and extension guards.

## Migration Files

| File | Purpose |
| --- | --- |
| `001_extensions.sql` | Enables `pgcrypto` and attempts `pgvector`. |
| `002_core_attio_mirror.sql` | Mirrors core Attio objects: users, organizations, people, deals, mandates. |
| `003_crm_roles.sql` | Adds buyer, seller, and investor/lender role tables. |
| `004_machine_layer.sql` | Adds Postgres-owned automation/intelligence tables. |
| `005_indexes.sql` | Adds lookup and relationship indexes. |

## Next Step

After dev RDS is created, fetch the RDS managed password from Secrets Manager,
build `DATABASE_URL`, run `migrate.ps1`, then run `validate.ps1`.
