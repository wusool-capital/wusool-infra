# Matching Engine

Backend for `/find-match`, used from Slack and from the web app (`client/`,
served at `/app`; see [Web app](#web-app) below). Given a buyer, checks its stored criteria against the advisor's
own typed context via the `discrepancies` module (a peer module, called
through `api/dependencies.py`, never owned here — see its own README),
extracts structured requirements via Bedrock, filters and scores
eligible sellers deterministically, asks Bedrock for narrative reasoning on
the top-N shortlist, persists the run, and posts the result to Slack with
Approve/Reject/View Full Analysis actions, or shows it on the web run page.

Not independently deployed — `server/main.py` merges this module's Slack
handlers with `ddl_commands`' onto one `AsyncApp` (one bot, one Slack app,
5 commands total). `bootstrap.py::create_app()` here exists only for running
this module in isolation (its own test suite / standalone dev).

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

```
matching_engine/
  bootstrap.py       # composition root — build_* factories, standalone create_app()
  config.py          # Settings (pydantic-settings)
  domain/            # entities, scoring, requirements — framework-free
  application/       # base.py (ServiceBase) + approvals.py/buyers.py/matching/
                       # use_cases.py/web_search.py (mixins) + service.py
                       # (MatchingEngineService facade) + application/ports/ Protocols.
                       # requirements.py/matching/reasoning_service.py stay standalone
                       # collaborator classes, not mixins — only MatchingMixin.run_match
                       # calls them. See base.py's docstring for why this module's
                       # ServiceBase constructor isn't as uniform as ddl_commands'.
  persistence/       # SQLAlchemy repositories + mappers, Unit-of-Work
  providers/         # bedrock/ (LLM) — the Firecrawl lead search moved to `discovery`
  api/                # router.py (aggregates health.py's router), Slack handlers,
                       # dependencies.py, http/ (the web app's /api/* routes)
  tests/
```

## Database

Connects to the shared `wusool_crm` PostgreSQL database (models in
`app/models/`, migrations in `alembic/`). This module never creates tables
or runs migrations itself — schema changes are the data engineer's call.
Reads/writes `buyer_roles`, `seller_roles`, `organizations`, `meetings`,
`match_scores`, `match_results` through its own repositories only. Approving
a match also upserts the `deals` row for the Qualified deal it creates in
Attio, and stamps `match_results.deal_attio_id`.

Each run and review decision also records an `activities` event
(`match.run_completed`, `match.approved`, `match.rejected`) linked to the
`match_results` row, on the same transaction. An approval that moves a deal's
stage records it in `deal_stage_events` too, comparing under a row lock so the
webhook echo of the same change records nothing. Writes go through
`app.modules.activities`; this module never inserts `activities` itself.

## Setup

Config comes from the repo-root `server/.env` (see `.env.example` there —
one env file for the whole backend). Relevant variables for this module:
`DATABASE_URL`, `SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `AWS_REGION`,
`AWS_BEDROCK_MODEL_ID_EXTRACTION`/`AWS_BEDROCK_MODEL_ID_REASONING`,
`AWS_ACCESS_KEY_ID`/`AWS_SECRET_ACCESS_KEY` (optional — omit to use the
standard AWS credential provider chain), `LLM_TEMPERATURE`/`LLM_MAX_TOKENS`/
`LLM_TOP_P`, `STAGE3_TOP_N`, `SCORING_WEIGHT_*`, `CONFIDENCE_*`,
`WEB_FALLBACK_MIN_SCORE` (this module's own threshold decision — the
Firecrawl lead search it triggers, and `FIRECRAWL_API_KEY`, belong to
`discovery` now), `MEETING_NOTES_MAX_CHARS`/
`MEETING_NOTES_MAX_TOTAL_CHARS`, `ENABLE_SELLER_MEETING_NOTES`,
`WEB_API_KEY` (the Toolkit secret's `env` map; a fallback to Slack sign-in),
`SLACK_CLIENT_ID`/`SLACK_CLIENT_SECRET`/`WEB_SESSION_SECRET`/`WEB_PUBLIC_URL`/
`WEB_SESSION_DAYS` (Sign in with Slack; all four strings are needed to turn it on),
`WEB_ALLOWED_ORIGINS` (CORS, empty for same-origin hosting),
`MATCH_RUN_STALE_AFTER_MINUTES` (default 15).

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
- `POST /slack/events` — Slack callback (signature-verified by Bolt).

The deployed process also serves the web app's `/api/*` routes, behind a
shared key (see [Web app](#web-app)).

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
   eliminate a candidate at Stage 1, but only if `source` is `crm_field`
   or `advisor_context` (an explicit constraint in the advisor's typed
   context) and `human_confirmed=True`). Typed context overrides the CRM:
   a criterion the advisor restates replaces the stored one
   (`domain/matching/overrides.py`), in the SQL narrowing too. A stated
   ticket range or EV cap (`advisor_limits`) replaces the stored check size
   or EV ceiling for that run. It counts only if the advisor's own words name
   what it measures (ticket/cheque, or EV/valuation); a bare "up to 10M" sets
   no limit, and the result message says so. and soft preferences (never eliminate, always
   just weighted). See `CRITERION_REGISTRY`
   (`domain/matching/scoring.py`) for the fixed set of checkable criteria.
3. **Candidate load + Stage 1 filtering** (one call) — SQL first narrows
   sellers on the buyer role's vertical, target region/country and EV ceiling
   (`domain/matching/narrowing.py`; a seller with no data for a dimension
   always passes). It also drops seller organizations already rejected for
   this buyer role (a `match_results` row with `decision = 'REJECTED'`);
   other buyer roles still see them. Cheque size never eliminates: `ticket_fit`
   (`domain/matching/ticket.py`) scores it in Stage 2 instead. Then a candidate is dropped only on a confirmed
   hard requirement's `Fail`; missing/unconfirmed data never eliminates
   anyone.
4. **Stage 2 scoring** — weighted average of per-criterion sub-scores
   (Pass=100/Fail=0/Unknown=50 neutral), same evaluator used for filtering
   so they never disagree. `data_confidence` is a separate signal (how much
   of the score rests on real CRM data vs LLM inference), never folded into
   ranking. Hard sector values (like geography) are OR-ed alternatives: the
   advisor's core business is hard, modifiers like "AI" are soft and only rank.
   Before top-N, a relevance gate drops candidates with no sector `Pass`
   whenever a hard sector exists; if none remain the run is empty and
   Google Maps discovery starts, searching the profile's `search_phrase`.
   The advisor's typed context outranks every CRM value for the criteria it
   restates (sector, geography, limits); stored values only fill the gaps.
5. **Reasoning** (Bedrock, one call) — narrative only for the top-N
   shortlist; cannot change scores, cannot invent facts not given to it.
6. **Persistence** — one atomic transaction: `match_scores` rows, linked
   `match_results` candidate rows, run marked complete.
7. **Slack delivery** — ranked result message with
   Approve/Reject/View Full Analysis/"Find more sellers". If every
   candidate scores below `WEB_FALLBACK_MIN_SCORE`, `discovery`'s lead
   search is triggered automatically (same button, same search, either
   way) — see `discovery/README.md`.
8. **Approve/Reject** — re-validates against the database (never trusts the
   Slack payload), atomic compare-and-set against `PENDING_REVIEW` so
   concurrent decisions can't race. Approve locks the candidate row (`SELECT … FOR UPDATE`) so a double
   click can't create two deals, then writes the Qualified Buy-side
   deal to Attio *first* (`deals.attio_id` is the Postgres primary key),
   then one Postgres transaction does the compare-and-set, the `deals`
   upsert and the `deal_attio_id` stamp. If Attio already has a deal for
   the buyer+seller pair, the approver chooses to promote it (only an
   `Inbound` deal moves; later stages are left alone) or create a new one.
   Attio-succeeds/Postgres-fails raises `PartialWriteError`; the inbound
   webhook / nightly resync reconciles the orphan. This path is its own
   (`providers/attio/deal_gateway.py`), not `lead_magnets`' deal writer,
   which never promotes a deal. Deal owner: `MATCHING_DEAL_OWNER_ID`.

Meeting notes (`meetings` table) are folded into both Bedrock prompts as
labeled, unverified context — always on for the buyer side, on by default
for shortlisted sellers (`ENABLE_SELLER_MEETING_NOTES=false` to restrict to
the buyer side only). Each summary is capped at `MEETING_NOTES_MAX_CHARS`
(default 3,000): a longer one keeps its first two thirds and its last third,
with a `[middle truncated]` marker between them, so next steps at the end
survive. Each prompt gets at most `MEETING_NOTES_MAX_TOTAL_CHARS` (default
12,000) of notes, newest first; the oldest note is always kept and the number
of dropped older meetings is stated in the prompt.

Not implemented, by design: pgvector/semantic retrieval, document
ingestion, general-purpose web scraping beyond `discovery`'s lead search,
structured seller-financial enrichment (see the `enrichment` module),
PDF generation, outreach/email.

## Web app

`client/` runs the same flow in the browser as one sequential page: buyer,
profile check, matching, shortlist, discovery, export. `server/main.py`
serves its build at `/app` (`api/http/spa.py`, with a fallback to
`index.html` for deep links) and includes `api/http/routes.py`.

Routes, all under `/api`. Sign-in lives in `api/http/auth_routes.py`
(`/api/auth/*`), and every other route needs a Slack session cookie
(`api/http/session.py`) or `Authorization: Bearer <WEB_API_KEY>`. A missing or
wrong one gets 401, and 503 comes back while neither is configured:

| Route | Does |
| --- | --- |
| `GET /buyers?q=` | Buyer search, the same lookup as `/find-match`. |
| `POST /buyers/{id}/preflight` | Discrepancy check against the advisor's note. A POST because conflicts depend on the note. |
| `POST /match-runs` | Starts a run: 202 with `run_id`. |
| `GET /match-runs/{id}` | Run state, candidates with reasoning, and discovery progress. |
| `POST /match-runs/{id}/discovery` | Starts discovery by hand ("Find more sellers"); a repeat is a no-op. |
| `POST /match-runs/{id}/candidates/{cid}/approve` | Approve. Takes the promote or create choice. |
| `POST /match-runs/{id}/candidates/{cid}/reject` | Reject. |
| `GET /match-runs/{id}/export.csv` | The candidates as CSV; repeat `fields` to choose and order columns. |

- **Who.** There is no login yet: decisions are recorded with
  `approved_by="web"` and runs with `requested_by` NULL.
- **Running a match.** `run_match` is split into `start_run` (commits the
  header row, returns the run id) and `execute_run` (the matching and its
  writes). Slack still calls `run_match`, which calls both. The web route
  returns after `start_run` and runs `execute_run` on the shared task runner.
- **Run state.** `match_results` has no running status, so a run with no
  `completed_at` is running, and after `MATCH_RUN_STALE_AFTER_MINUTES` it is
  reported as stale (lost to a restart). `FAILED` is failed.
- **Discovery.** A web run whose scores are all below `WEB_FALLBACK_MIN_SCORE`
  starts discovery automatically, as Slack does, without posting to Slack.
  Its progress and the run's advisor notes are kept in an in-process tracker
  (`api/http/run_tracker.py`). A restart loses it; the run page then offers
  **Find more sellers** to start the search by hand. Runs that cleared the
  threshold offer it too, like Slack's button. Both paths call
  `api.dependencies.discover_sellers_for_run`, which runs the search, adds
  the new sellers to the run and returns a `RunDiscovery`. Slack posts it as
  messages; the web keeps it in the tracker. One run never searches twice:
  the search is claimed on the run row's `metadata.discovery`, atomically and
  across restarts. A search that created sellers keeps the claim and its
  outcome and notes. Anything else releases it so it can be retried, for
  example after the daily cap. A claim with no outcome expires after
  `MATCH_RUN_STALE_AFTER_MINUTES`.
- **Double submits.** `POST /match-runs` takes a client `request_id`; a
  repeat with it returns the first run. Approve and Reject are guarded by the
  row's status, so a repeat gets 409 `already_reviewed`.
- **Slack parity.** `GET /match-runs/{id}` returns the requirement profile
  (`mandate`), each scored candidate's `criteria` and every candidate's
  `profile` (`SellerRepositoryPort.get_profiles`). Approving a discovered
  seller runs `enrich_and_post` into `WEB_REVIEW_CHANNEL_ID`, skipped when
  unset.
- **Existing deal.** Approve returns 409 with the existing Attio deals; the
  page asks to promote one or create a new deal, the same choice Slack offers.
- **Export.** Cells starting with `=`, `+`, `-` or `@` are prefixed with `'`
  so LLM text can't run as a spreadsheet formula.
- **Deploys.** Runs are in-process: a deploy or restart mid-run leaves a stale
  run that the advisor restarts. A real job queue is the follow-up.

## Where to go next

New to this module? See [`HOW-TO-READ.md`](HOW-TO-READ.md).
