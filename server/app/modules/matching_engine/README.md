# Matching Engine

Backend for `/find-match` — Slack is the only product interface, no
frontend. Given a buyer, extracts its structured requirements via Bedrock,
filters and scores eligible sellers deterministically, asks Bedrock for
narrative reasoning on the top-N shortlist, persists the run, and posts the
result to Slack with Approve/Reject/View Full Analysis actions.

Not independently deployed — `server/main.py` merges this module's Slack
handlers with `ddl_commands`' onto one `AsyncApp` (one bot, one Slack app,
5 commands total). `bootstrap.py::create_app()` here exists only for running
this module in isolation (its own test suite / standalone dev).

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
matching_engine/
  bootstrap.py       # composition root — build_* factories, standalone create_app()
  config.py          # Settings (pydantic-settings)
  domain/            # entities, scoring, requirements — framework-free
  application/       # use cases + application/ports/ Protocols
  persistence/       # SQLAlchemy repositories + mappers, Unit-of-Work
  providers/         # bedrock/ (LLM), firecrawl/ (web fallback)
  api/                # FastAPI routes, Slack handlers, dependencies.py
  tests/
```

## Database

Connects to the shared `wusool_crm` PostgreSQL database (models in
`app/models/`, migrations in `alembic/`). This module never creates tables
or runs migrations itself — schema changes are the data engineer's call.
Reads/writes `buyer_roles`, `seller_roles`, `organizations`, `meetings`,
`match_scores`, `match_results` through its own repositories only.

## Setup

Config comes from the repo-root `server/.env` (see `.env.example` there —
one env file for the whole backend). Relevant variables for this module:
`DATABASE_URL`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `AWS_REGION`,
`AWS_BEDROCK_MODEL_ID_EXTRACTION`/`AWS_BEDROCK_MODEL_ID_REASONING`,
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (optional — omit to use the
standard AWS credential provider chain), `LLM_TEMPERATURE`/`LLM_MAX_TOKENS`/
`LLM_TOP_P`, `STAGE3_TOP_N`, `SCORING_WEIGHT_*`, `CONFIDENCE_*`,
`FIRECRAWL_API_KEY` (optional — omit to disable the web-fallback lead
search entirely), `WEB_FALLBACK_MIN_SCORE`, `MEETING_NOTES_MAX_CHARS`/
`MEETING_NOTES_MAX_TOTAL_CHARS`, `ENABLE_SELLER_MEETING_NOTES`.

Bedrock needs `bedrock-runtime:Converse` on the two configured model IDs —
deploy with an IAM role/task role attached rather than static AWS keys;
those are for local dev only.

## Running standalone (dev/testing only)

```bash
uv run uvicorn --factory app.modules.matching_engine.bootstrap:create_app --reload
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias `/ready`) — confirms database connectivity, 503
  if unreachable.
- `POST /slack/events` — Slack callback (signature-verified by Bolt); never
  exposed as a public REST API for match/buyer/seller data.

The actually-deployed process is `server/main.py`, one Slack app serving
this module's `/find-match` plus `ddl_commands`' 4 commands together.

## Testing

```bash
uv run pytest
```

Runs with dummy config, no live database/Slack/AWS credentials required.
DB-backed integration tests skip cleanly when `DATABASE_URL` is unreachable
(no SSM tunnel open) rather than failing.

## Matching pipeline, in brief

1. **Buyer resolution** — fuzzy search by name; 0/1/many results branch to
   "not found" / run / disambiguation modal.
2. **Requirement extraction** (Bedrock, one call) — buyer's structured
   fields + free text + recent meeting notes → hard requirements (can
   eliminate a candidate at Stage 1, but only if `source="crm_field"`/
   `human_confirmed=True`) and soft preferences (never eliminate, always
   just weighted). See `CRITERION_REGISTRY`
   (`domain/matching/scoring.py`) for the fixed set of checkable criteria.
3. **Stage 1 filtering** — drop a candidate only on a confirmed hard
   requirement's `Fail`; missing/unconfirmed data never eliminates anyone.
4. **Stage 2 scoring** — weighted average of per-criterion sub-scores
   (Pass=100/Fail=0/Unknown=50 neutral), same evaluator used for filtering
   so they never disagree. `data_confidence` is a separate signal (how much
   of the score rests on real CRM data vs LLM inference), never folded into
   ranking.
5. **Reasoning** (Bedrock, one call) — narrative only for the top-N
   shortlist; cannot change scores, cannot invent facts not given to it.
6. **Persistence** — one atomic transaction: `match_scores` rows, linked
   `match_results` candidate rows, run marked complete.
7. **Slack delivery** — ranked result message with
   Approve/Reject/View Full Analysis, or, if every candidate scores below
   `WEB_FALLBACK_MIN_SCORE`, up to 3 unverified Google-Maps leads via
   Firecrawl instead (never persisted, shown once).
8. **Approve/Reject** — re-validates against the database (never trusts the
   Slack payload), atomic compare-and-set against `PENDING_REVIEW` so
   concurrent decisions can't race.

Meeting notes (`meetings` table) are folded into both Bedrock prompts as
labeled, unverified context — always on for the buyer side, on by default
for shortlisted sellers (`ENABLE_SELLER_MEETING_NOTES=false` to restrict to
the buyer side only).

Not implemented, by design: pgvector/semantic retrieval, document
ingestion, general-purpose web scraping beyond the one Firecrawl fallback,
structured seller-financial enrichment, PDF generation, outreach/email.
