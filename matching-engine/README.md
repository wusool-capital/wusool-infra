# Matching Engine

Backend for the Buyer-Seller Matching & Intelligence Platform. Slack is the
only product interface; there is no frontend in this repository.

This is Branch 1. Phase 2 maps the application onto the existing database —
see [Phase 2 scope](#phase-2-scope) below. It does not yet implement the
`/find-match` workflow, matching algorithm, or LLM calls.

## Stack

Python 3.12+, FastAPI, SQLAlchemy 2.x (async, `asyncpg`), Pydantic v2, Slack
Bolt, boto3 (AWS Bedrock), `uv`, `pytest`, `ruff`.

## Database

The application connects to the existing `wusool_crm` PostgreSQL database
(see `../scripts/db/README.md` at the repo root for schema and sync
details). This application **never** creates tables, runs migrations, or
resets schema — that database is owned and evolved outside this codebase.

**Schema gap:** a `PRD.md` at the repo root describes a richer target schema
(versioned `buyer_requirement_profiles`/`seller_profiles`, `match_runs`,
`matches`, `match_evidence`, `approvals`, document chunking) that was never
actually implemented in `wusool_crm`. This application maps the real,
existing tables as they are — `buyer_roles`/`seller_roles` (flat, one row
per organization, no versioning) and `match_scores` (the only match-related
table; no run grouping, no evidence table, no approvals table at all). See
docstrings in `app/shared/database/models/` and each module's
`infrastructure/models.py` for the specifics, table by table.

Schema-drift detection (`app/shared/database/schema_check.py`) runs at test
time against a live database (`tests/integration/test_schema_drift.py`),
deliberately not at app startup — keeping this app booting with no DB
reachable (see `/readiness` below) stays load-bearing for local dev without
an SSM tunnel.

The database may contain pgvector-related tables/columns from other
workstreams. This application does not depend on them.

## Setup

```bash
cd matching-engine
uv sync
cp .env.example .env  # then fill in real values
```

## Running

```bash
uv run uvicorn app.main:app --reload
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` — confirms database connectivity (`SELECT 1`); returns
  503 if unreachable (e.g. no SSM tunnel open in dev).

## Testing

```bash
uv run pytest
```

The suite runs with dummy configuration and no live database or Slack/AWS
credentials required — `tests/integration/`'s DB-backed tests skip cleanly
when the database is unreachable (e.g. no SSM tunnel open) rather than
failing, and run for real against `wusool_crm` when one is.

## Structure

Modular monolith: each module in `app/modules/` owns its domain,
application, and infrastructure layers. FastAPI and Slack are adapters
around application services — business logic never lives in a route or
Slack handler directly. See the repository-root Wusool infra
[README](../README.md) for how this fits into the broader CRM/data
platform.

## Phase 2 scope

Implemented: ORM models for `Organization`, `Person`, `Deal`, `Mandate`,
`BuyerRole`, `SellerRole`, `MatchScore` (typed declarative style, real
columns only); repositories for buyers/sellers/matching; Pydantic read
schemas and infra-independent domain value objects; schema-drift test;
AWS Bedrock config/client boundary (construction only, no calls,
replacing the direct Anthropic integration).

Not implemented (by design, given the schema gap above): approvals
persistence (no table), versioned requirement/seller profiles (no version
column exists), match-run audit trail (no table), the `/find-match` Slack
workflow, the matching algorithm itself, LLM extraction/reasoning calls,
Attio synchronization.

## Phase 1 scope

Implemented: configuration, FastAPI entrypoint with health/readiness,
database connectivity wiring (no schema), module/package boundaries, Slack
Bolt app construction (handlers unregistered), integration boundaries,
boot tests.
