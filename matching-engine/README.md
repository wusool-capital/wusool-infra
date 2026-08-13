# Matching Engine

Backend for the Buyer-Seller Matching & Intelligence Platform. Slack is the
only product interface; there is no frontend in this repository.

This is Branch 1: a modular-monolith skeleton. It does not yet implement
matching, Slack workflows, or LLM business logic — see
[Phase 1 scope](#phase-1-scope) below.

## Stack

Python 3.12+, FastAPI, SQLAlchemy 2.x (async, `asyncpg`), Pydantic v2, Slack
Bolt, Anthropic SDK, `uv`, `pytest`, `ruff`.

## Database

The application connects to the existing `wusool_crm` PostgreSQL database
(see `../scripts/db/README.md` at the repo root for schema and sync
details). This application **never** creates tables, runs migrations, or
resets schema — that database is owned and evolved outside this codebase.
Schema mapping to application models is Phase 2.

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

The suite runs with dummy configuration and no live database or Slack/LLM
credentials required.

## Structure

Modular monolith: each module in `app/modules/` owns its domain,
application, and infrastructure layers. FastAPI and Slack are adapters
around application services — business logic never lives in a route or
Slack handler directly. See the repository-root Wusool infra
[README](../README.md) for how this fits into the broader CRM/data
platform.

## Phase 1 scope

Implemented: configuration, FastAPI entrypoint with health/readiness,
database connectivity wiring (no schema), module/package boundaries, Slack
Bolt app construction (handlers unregistered), Anthropic client boundary,
Attio integration boundary, boot tests.

Not implemented: matching endpoints, `/find-match` Slack workflow, buyer
requirement extraction, deterministic scoring/confidence, LLM reasoning,
Attio synchronization, ORM models mapped to the real schema.
