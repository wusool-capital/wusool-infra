# Attio and database sync

## Purpose

Attio is the business-facing CRM of record. PostgreSQL (`wusool_crm`) is the
application mirror used for matching, Toolkit workflows, meeting processing,
and lead-tool bookkeeping.

## Components

| Component | Role |
| --- | --- |
| Attio provider module | API calls, payload conversion, object/list lookup, webhook verification, and notes. |
| `ddl_commands` sync persistence | Maps Attio objects and list entries into PostgreSQL. |
| `POST /webhooks/attio` | Applies supported Attio changes in near real time. |
| Source Attio scripts | Ensure/validate the SOURCE schema, sync lists/objects, and backfill approved fields. |
| PostgreSQL sync scripts | Copy and validate approved SOURCE data in development and production. |
| Alembic | Owns PostgreSQL schema changes; runtime code never alters tables. |

The CRM schema documentation is authoritative for exact Attio attribute/list
slugs, PostgreSQL columns, and migration decisions.

## Data flow

- Direct CRM edits arrive through the signature-verified webhook.
- A scheduled full synchronization repairs missed or reordered events.
- Toolkit add/edit operations write Attio first, then PostgreSQL.
- Lead tools record a `tool_runs` ledger entry, write entities to Attio, and
  rely on the webhook/full sync for the complete mirror.
- WusoolScribe meeting processing writes a CRM note, including meetings with no
  resolved organization.

One SOURCE workspace contains test and production records. `is_test` is always
set on system-created records. Each environment reads only its own side; an
unset flag belongs to neither filtered view and is a data-quality error.

## Dependencies and configuration

The application uses `ATTIO_API_KEY`, `ATTIO_WEBHOOK_SECRET`, optional
`ATTIO_WORKSPACE_ID`, `ATTIO_IS_TEST`, and `DATABASE_URL`. Sync scripts
require explicit source/target access supplied through their operator
environment. Credentials stay outside the repository.

PostgreSQL model changes require reviewed Alembic migrations. Attio schema
changes require synchronized target-schema, mapping, decision-log, validation,
and client-overview updates.

## Interfaces

`POST /webhooks/attio` is the only public sync endpoint. It verifies the
Attio signature and, when configured, the workspace ID. Other sync surfaces are
operator scripts under `infrastructure/crm-sync/scripts/source-attio` and
`server/scripts/postgres-sync`.

The integration supports create/update synchronization for the approved model.
It is not unrestricted CRM CRUD: Toolkit removal commands are absent, and
record deletion is not a general client interface.

### Example synchronization path

An operator updates a seller field in Attio. The signed webhook validates the
workspace and updates the matching PostgreSQL row. If delivery is missed or
arrives out of order, the next full synchronization compares the approved
fields and converges the mirror. A later `/find-match` request reads the
corrected PostgreSQL value.

If Attio shows the change but PostgreSQL does not, preserve the record ID,
field, value, and edit time. Check webhook processing and full-sync validation
before editing PostgreSQL directly, because the next sync can overwrite a
database-only correction.

## Processing and failures

- Invalid signatures or workspace IDs are rejected before mutation.
- Attio-first writes can partially succeed across multiple remote records; the
  Toolkit reports what landed, and later synchronization converges PostgreSQL.
- PostgreSQL-only edits to mirrored fields can be overwritten by full sync.
- Validation scripts compare counts, relationships, required values, and
  environment flags. Failed validation blocks completion.
