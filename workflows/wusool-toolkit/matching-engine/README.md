# Matching Engine

Backend for the Buyer-Seller Matching & Intelligence Platform. Slack is the
only product interface; there is no frontend in this repository.

This is Branch 1. Phase 3 connects the backend to Slack and implements the
full `/find-match` product loop — see [Phase 3 scope](#phase-3-scope) below.

## Stack

Python 3.12+, FastAPI, SQLAlchemy 2.x (async, `asyncpg`), Pydantic v2, Slack
Bolt, boto3 (AWS Bedrock), `uv`, `pytest`, `ruff`.

## Database

The application connects to the existing `wusool_crm` PostgreSQL database
(see `../../../database/README.md` for schema and sync details). This
application **never** creates tables, runs migrations, or resets schema —
that database is owned and evolved outside this codebase.

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

### Required environment variables

See `.env.example` for the full list with defaults. At minimum:

| Variable | Purpose |
| --- | --- |
| `DATABASE_URL` | `wusool_crm` connection string (either `postgresql://` or `postgresql+asyncpg://` — normalized automatically) |
| `SLACK_BOT_TOKEN` | Bot token (`xoxb-...`) from your Slack app |
| `SLACK_SIGNING_SECRET` | Used to verify every incoming Slack request (§2/§37 — never disable this) |
| `AWS_REGION` | Defaults to `eu-central-1`, matching the already-provisioned Bedrock access |
| `AWS_BEDROCK_MODEL_ID_EXTRACTION` / `AWS_BEDROCK_MODEL_ID_REASONING` | Bedrock model/inference-profile IDs; defaults match `terraform/modules/bedrock-access` |
| `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` | Optional — omit to use the standard AWS credential provider chain (IAM role, ECS/EC2 task role, local profile). Never require long-lived credentials in production |
| `STAGE3_TOP_N` | How many shortlisted candidates go to Bedrock reasoning (default 3) |
| `FIRECRAWL_API_KEY` | Optional — enables the Google-Maps web-fallback lead search (see below). Omit to disable it entirely; the pipeline then just shows "no qualifying candidates" as before |
| `WEB_FALLBACK_MIN_SCORE` | Score threshold (default 50.0) below which every CRM candidate is considered non-qualifying and the web fallback triggers |
| `MEETING_NOTES_MAX_CHARS` / `MEETING_NOTES_MAX_TOTAL_CHARS` | Per-note and total-section character caps for meeting-notes enrichment (defaults 600 / 4000) |
| `ENABLE_SELLER_MEETING_NOTES` | On by default (`true`) — attaches meeting notes to shortlisted seller candidates' reasoning narrative too, not just the buyer's. Set to `false` to restrict enrichment to the buyer side only (see below) |

### Configuring the Slack app

1. Create a Slack app (or use an existing one) at api.slack.com/apps.
2. **Slash Commands** → create `/find-match`, request URL
   `https://<your-host>/slack/events`.
3. **Interactivity & Shortcuts** → enable, same request URL
   `https://<your-host>/slack/events` (handles button clicks and the buyer
   disambiguation modal's submission).
4. **OAuth & Permissions** → bot token scopes: `commands`, `chat:write`.
   Install the app to your workspace; copy the bot token into
   `SLACK_BOT_TOKEN`.
5. **Basic Information** → copy the Signing Secret into
   `SLACK_SIGNING_SECRET`.

### Configuring AWS/Bedrock permissions

The backend calls `bedrock-runtime:Converse` against the two configured
model IDs. `terraform/modules/bedrock-access` already provisions an
`InvokeBedrockModels` IAM policy (`bedrock:InvokeModel`,
`bedrock:InvokeModelWithResponseStream`) scoped to the model/inference-profile
ARNs — attach it to whatever role/instance runs this backend. Deploy with
that role attached (IAM role / ECS or EC2 task role) rather than static
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` — those two are for local dev
only, and optional even then if you have a local AWS profile configured.

## Running

```bash
uv run uvicorn app.main:app --reload
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias: `GET /ready`) — confirms database connectivity
  (`SELECT 1`); returns 503 if unreachable (e.g. no SSM tunnel open in dev).
- `POST /slack/events` — the Slack callback endpoint (slash commands,
  interactive actions, view submissions). Signature-verified by Bolt; never
  exposed as a public REST API for matching/buyer/seller/approval data (§29).

### Running with Docker Compose

```bash
docker compose up --build
```

Builds the app from the `Dockerfile` and starts it alongside a throwaway
Postgres (`pgvector/pgvector:pg16` — plain `postgres:16-alpine` lacks the
extension, which is fatal to Postgres's own init-script runner, unlike the
manual `docker exec` loop below) that auto-applies `database/sql/*.sql` on
first start. The app's `DATABASE_URL` always points at that bundled `db`
service, not whatever's in your `.env` — real Slack/AWS credentials still
come from your environment or a `.env` file (`SLACK_BOT_TOKEN`,
`SLACK_SIGNING_SECRET`, `AWS_*`) if you want to exercise real integrations;
otherwise it starts with harmless local-dev defaults. `docker compose down
-v` tears down both containers and the DB volume.

## Testing

```bash
uv run pytest
```

The suite runs with dummy configuration and no live database or Slack/AWS
credentials required — `tests/integration/`'s DB-backed tests skip cleanly
when the database is unreachable rather than failing, and run for real
against `wusool_crm` when a tunnel is open.

### Running the DB-backed tests locally with Docker

No SSM tunnel needed for local iteration — spin up a throwaway Postgres,
apply the same schema files the real database uses, and point
`DATABASE_URL` at it:

```bash
docker run -d --name matching-engine-test-db \
  -e POSTGRES_USER=matching -e POSTGRES_PASSWORD=matching -e POSTGRES_DB=wusool_crm \
  -p 55432:5432 postgres:16-alpine

for f in ../../../database/sql/*.sql; do
  docker exec -i matching-engine-test-db psql -U matching -d wusool_crm -v ON_ERROR_STOP=1 < "$f"
done

export DATABASE_URL="postgresql://matching:matching@localhost:55432/wusool_crm"
uv run pytest tests/integration
```

The container starts empty (no seed data, matching the real database's own
"never seed" rule) — most DB-backed tests then skip with "no ... found in
the database" rather than failing. Insert a minimal row or two directly via
`psql` if you want them to actually exercise their logic instead of
skipping; never do this against the real `wusool_crm`. `pgvector` isn't
available in the plain `postgres:16-alpine` image — `001_extensions.sql`
degrades gracefully (harmless, out of scope for Branch 1 either way).

### Invoking `/find-match`

In Slack: `/find-match <buyer name>` (e.g. `/find-match Acme Capital`).
- No match → an ephemeral "No buyer found" message.
- One match → the matching workflow runs in the background and posts a
  top-3 result message with score/confidence/rationale and
  Approve/Reject/View Full Analysis buttons — or, if every candidate scores
  below `WEB_FALLBACK_MIN_SCORE`, up to 3 unverified web-sourced leads
  instead (see "Web fallback (Firecrawl)" below).
- Multiple matches → a selection modal; submitting it runs the same
  workflow for the chosen buyer.

## Meeting-notes enrichment

Free-text call/meeting notes (`meetings` table — Attio-migrated notes plus
the in-house Scribe recorder, hard-FK'd to `organizations`) are folded into
the Bedrock prompts as additional unverified context, on top of the buyer's
own CRM `investment_strategy`/`notes` fields:

- **Buyer side (always on):** the buyer's org's recent meeting notes are
  fetched at resolution time (`MeetingRepository.get_recent_by_org`) and
  appended, clearly labeled ("context only, not verified CRM data — may also
  describe other organizations"), to both the requirement-extraction and
  reasoning prompts. The extraction prompt explicitly instructs the LLM to
  fold anything derived only from a meeting note into `strategic_thesis`/
  `ideal_target_description` (or, if it must become a structured
  requirement, mark it `human_confirmed: false`) — never invent a new
  criterion outside `CRITERION_REGISTRY` from note text.
- **Seller side (on by default, `ENABLE_SELLER_MEETING_NOTES=false` to
  disable):** the same notes, fetched only for the already-shortlisted
  top-N candidates (never all eligible sellers), are appended to the
  reasoning prompt's per-candidate context — narrative only, never scoring
  or Stage 1 filtering input.
- **Selection, not a fixed top-N:** all of an org's notes are fetched, then
  a total character budget (`MEETING_NOTES_MAX_TOTAL_CHARS`) is filled
  greedily from most recent, while always keeping the *oldest* note too (a
  founding/mandate-defining note shouldn't drop just because more recent,
  narrower ones exist). Omitted/truncated notes are always stated in the
  prompt (`(N older meetings omitted)`, `[truncated]`), never silently
  dropped.
- No pre-combine LLM pass and no embeddings/vector recall — see
  `app/shared/types/meeting_note.py` for the budget-selection logic, which
  is a pure function, no extra Bedrock call.

## Web fallback (Firecrawl)

When every CRM seller candidate's score falls below `WEB_FALLBACK_MIN_SCORE`
(including the case of zero surviving candidates), the pipeline scrapes
Google Maps via Firecrawl (`app/modules/web_search/`) for up to 3 potential
seller leads and shows them in Slack instead of the normal ranked-candidate
message, clearly labeled "Not yet in CRM, unverified" with a link to each
listing. These leads are never persisted (no `match_results`/`match_scores`
rows) — shown once, logged, and gone. Disabled entirely (falls back to the
plain "no qualifying candidates" message) if `FIRECRAWL_API_KEY` is unset.

## Structure

Modular monolith: each module in `app/modules/` owns its domain,
application, and infrastructure layers. FastAPI and Slack are adapters
around application services — business logic never lives in a route or
Slack handler directly. See the repository-root Wusool infra
[README](../../../README.md) for how this fits into the broader CRM/data
platform.

## Phase 3 scope

The full Branch 1 product loop end-to-end:
`/find-match` → buyer resolution (0/1/many) → Slack disambiguation modal if
needed → Bedrock requirement extraction (strict Pydantic validation, one
bounded repair retry, fail-closed) → Stage 1 structured filtering
(missing-data pass-through is mandatory — NULL never eliminates a candidate)
→ Stage 2 deterministic scoring + data confidence (a separate signal from
score, never combined) → top-N shortlist → Bedrock reasoning (mocked in
tests) → persistence (one atomic transaction for the shortlist + its linked
`match_scores` rows + the run's completion) → Slack result message → View
Full Analysis / Approve / Reject, enforcing an explicit state machine
(`GENERATED → PENDING_REVIEW → APPROVED/REJECTED`, never `APPROVED →
GENERATED`) independent of the database `CHECK` constraint.

One new, additive table was required and added by the DB team:
`match_results` (run audit + shortlisted candidates + status + approval —
see `workflows/crm-sync/docs/PHASE3_MATCH_RESULTS_HANDOVER.md` for the full design
rationale). Evidence and the deterministic scoring breakdown still live on
the pre-existing `match_scores` table, exactly as Phase 2 scoped it.

Architectural seams built for Branch 2 without implementing it: a
`CandidateRetriever` Protocol (Stage 1's `StructuredCandidateRetriever` is
the only implementation; a future `HybridCandidateRetriever` with semantic
retrieval slots in without changing the orchestrator, scoring, or Slack
layer), and a `TaskRunner` Protocol (`InProcessTaskRunner` today; a durable
queue/worker can replace it without touching any use case).

Added after initial Phase 3 scoping (see "Meeting-notes enrichment" and "Web
fallback (Firecrawl)" above): free-text meeting-notes context in both
Bedrock prompts, and a narrow, Google-Maps-only web-scraping fallback for
buyers with no qualifying CRM seller. Neither uses pgvector/embeddings —
still explicitly out of scope, along with everything else below.

Not implemented (out of scope for Branch 1 by design): pgvector/embeddings/
semantic retrieval/RAG, document ingestion, Drive polling, general-purpose
website scraping beyond the one Firecrawl fallback above, Attio
synchronization/write-back, structured seller financial enrichment (the
`buyer_intel`/`seller_financials` tables from `004_machine_layer.sql` remain
unused), PDF generation, emails or any outreach to buyers/sellers, background
worker infrastructure beyond the in-process task runner.

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
