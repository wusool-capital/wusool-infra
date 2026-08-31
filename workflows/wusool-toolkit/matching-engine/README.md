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
(see `../../../database/README.md` for schema, Alembic migrations, and sync
details). This application **never** creates tables, runs migrations, or
resets schema itself — the schema is owned by `database/wusool_db/` and
evolved there via Alembic, wired into CD; this app only imports the models
from that package (`app.shared.database.registry.import_all_models()` →
`wusool_db.models`) and reads/writes through them.

**Schema gap:** a `PRD.md` at the repo root describes a richer target schema
(versioned `buyer_requirement_profiles`/`seller_profiles`, `match_runs`,
`matches`, `match_evidence`, `approvals`, document chunking) that was never
actually implemented in `wusool_crm`. This application maps the real,
existing tables as they are — `buyer_roles`/`seller_roles` (flat, one row
per organization, no versioning) and `match_scores` (the only match-related
table; no run grouping, no evidence table, no approvals table at all). See
docstrings in `database/wusool_db/models/` for the specifics, table by
table — this app no longer defines any model of its own.

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

This app is not deployed standalone — it's one of two folders behind a
single Slack bot together with `../ddl-commands/` (see `../README.md`). One
Slack app serves `/find-match` (this folder) plus `/edit-seller`,
`/edit-buyer`, `/add-seller`, `/add-buyer` (ddl-commands); see
`../../../docs/SLACK_APP_SETUP.md` at the repo root for the full setup checklist
covering all 5 commands under that one app.

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

Running just this folder in isolation (for dev/testing only — see
`../README.md` for how the deployed bot actually runs, off `../main.py`):

```bash
uv run uvicorn app.main:app --reload
```

- `GET /health` — liveness, no database dependency.
- `GET /readiness` (alias: `GET /ready`) — confirms database connectivity
  (`SELECT 1`); returns 503 if unreachable (e.g. no SSM tunnel open in dev).
- `POST /slack/events` — the Slack callback endpoint (slash commands,
  interactive actions, view submissions). Signature-verified by Bolt; never
  exposed as a public REST API for matching/buyer/seller/approval data (§29).

### Running the actual bot (both folders, one process)

```bash
cd ..  # workflows/wusool-toolkit
docker compose up --build
```

Builds the merged image from the root `Dockerfile` (both this folder and
`../ddl-commands/`) and starts it alongside a throwaway Postgres
(`pgvector/pgvector:pg16` — plain `postgres:16-alpine` lacks the extension,
which is fatal to Postgres's own init-script runner) that auto-applies
`database/sql/*.sql` on first start. `DATABASE_URL` always points at that
bundled `db` service, not whatever's in your `.env` — real Slack/AWS
credentials still come from your environment or a root `.env` file
(`SLACK_BOT_TOKEN`, `SLACK_SIGNING_SECRET`, `AWS_*`) if you want to exercise
real integrations; otherwise it starts with harmless local-dev defaults.
`docker compose down -v` tears down both containers and the DB volume.

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

## Scoring rubric

`CRITERION_REGISTRY` (`app/modules/matching/domain/scoring.py`) is the
single source of truth for every criterion this engine can actually check.
The extraction prompt is built from this same registry
(`describe_criteria()`), so the LLM is never told about — or free to
invent — a criterion name the scoring engine can't evaluate.

| Criterion | Checked against seller's... |
|---|---|
| `revenue` | `est_revenue` (threshold) |
| `ebitda` | `est_ebitda` (threshold) |
| `geography` | `geographic_focus` / `hq_country` |
| `sector` | `sector_focus` |
| `sector_exclusion` | `sector_focus` (inverse — must NOT match) |
| `client_type` | `client_type` |
| `outreach_tier` | `outreach_tier` |
| `relationship_status` | `relationship_status` |
| `appetite_signal` | `appetite_signal` |

**Per-criterion sub-score** (same evaluator used for both Stage 1 filtering
and Stage 2 scoring, so they never disagree):
- **Pass** → 100
- **Fail** → 0
- **Unknown**/unavailable (seller field not populated, or the requirement's
  own value is missing) → **50 (neutral)** — missing data never counts
  against a candidate.

**`overall_score`** = weighted average of every sub-score:
`Σ(weight × sub_score) / Σ(weight)`. Hard requirements always weight
`1.0`; soft preferences use whatever weight the LLM assigned per-preference
in `scoring_rubric`.

**`data_confidence`** = weighted average of a confidence multiplier per
criterion, using the same weights as the score:
- `crm_field` → 1.0 (fixed, not configurable)
- `unavailable` → 0.0 (fixed, not configurable)
- `llm_extracted` → 0.6 (default, configurable via `CONFIDENCE_...` env vars)
- `llm_inferred` → 0.4 (default, configurable)

One precise, worth-knowing detail: in the current implementation,
`_evaluate_criterion` (the function that checks seller-side data) only
ever returns `crm_field` or `unavailable` as the data-backing for a
criterion — never `llm_extracted`/`llm_inferred`. So per-criterion
confidence today is effectively **binary**: 100% if the seller's relevant
CRM field is populated, 0% if not. The `llm_extracted`/`llm_inferred`
multipliers exist in `Settings.confidence` but aren't currently reachable
through this exact scoring path.

An unrecognized criterion name (anything outside the 9 above) is recorded
for audit (`result="Unrecognized"`, visible in View Full Analysis) but
excluded entirely from `weighted_sum`/`total_weight`/`data_confidence` —
it never fabricates a neutral 50 that would silently dilute the real score.

## Hard vs. soft requirements

Bedrock's extraction step (`app/modules/requirements/`) reads a buyer's
structured CRM fields plus all free text and sorts what it finds into two
lists, both scored against `CRITERION_REGISTRY`'s 9 recognized criteria
(`revenue`, `ebitda`, `geography`, `sector`, `sector_exclusion`,
`client_type`, `outreach_tier`, `relationship_status`, `appetite_signal`):

- **Hard requirement** — a dealbreaker ("must be UAE-based"). Always
  weight `1.0` in scoring. Can only *eliminate* a candidate at Stage 1 if
  `source="crm_field"`/`human_confirmed=True` — i.e. it came from a real
  structured field, not something the LLM inferred from prose.
- **Soft preference** — a stated bias, never a dealbreaker ("prefers
  founder-led operators"). Weight is whatever the LLM assigned in
  `scoring_rubric`. Never eliminates anyone, regardless of confirmation.

**Elimination rule, precisely** (`apply_structured_filters` in
`app/modules/matching/domain/scoring.py`): a candidate is dropped **only**
if a `human_confirmed=True` hard requirement returns a confirmed `Fail`. An
`llm_extracted`/`llm_inferred` hard requirement's result — pass, fail, or
unknown — is never evaluated for elimination at all:

| Hard req #1 (`crm_field`) | Hard req #2 (`llm_extracted`) | Stage 1 outcome |
|---|---|---|
| Pass | Fail | **Survives** — req #2's result is invisible to Stage 1 |
| Pass | Pass | Survives |
| **Fail** | Pass | **Dropped** — because of req #1, not req #2 |
| **Fail** | Fail | **Dropped** — same reason; req #2 still isn't why |

An unconfirmed hard requirement's `Fail` isn't ignored, though — it's still
evaluated at Stage 2 scoring with full weight, where it can lower a
candidate's rank (a `Fail` sub-score of 0 vs. an `Unknown`/unavailable
neutral 50) but never remove them from the shortlist. This is the same
"only independently-verifiable facts can disqualify someone" rule applied
consistently — free text can make a candidate look worse, never disappear.

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

Trigger, exactly (`needs_web_fallback` in `app/modules/matching/domain/scoring.py`):

```python
def needs_web_fallback(scores: list[float], min_score: float) -> bool:
    return not scores or max(scores) < min_score
```

The **highest** `overall_score` in the shortlist — not an average — is
compared against `WEB_FALLBACK_MIN_SCORE` (**default 50.0**). If even the
best candidate doesn't clear that bar, or the shortlist is empty outright,
the fallback fires. This checks score *quality*, not just presence: a
non-empty shortlist doesn't mean a good match — free-text-derived hard
requirements can't eliminate candidates at Stage 1 (see "Hard vs. soft
requirements" above), so a shortlist can survive Stage 1 while every
candidate is still a poor fit.

When it fires, the pipeline scrapes Google Maps via Firecrawl
(`app/modules/web_search/`) for up to 3 potential seller leads and shows
them in Slack instead of the normal ranked-candidate message, clearly
labeled "Not yet in CRM, unverified" with a link to each listing. These
leads are never persisted (no `match_results`/`match_scores` rows) — shown
once, logged, and gone. If Firecrawl returns nothing, the normal
low-scoring ranked list is shown instead of a dead end. Disabled entirely
(always shows the plain ranked list, never the fallback) if
`FIRECRAWL_API_KEY` is unset.

**How the scrape itself works** (`app/modules/web_search/`):

1. **Build a query** — `_extract_query_terms` (`lead_search_service.py`)
   pulls `sector`/`geography` straight from the buyer's already-extracted
   `RequirementProfile` (the same 9-criterion registry scoring uses), e.g.
   `"healthcare companies Saudi Arabia"`. Falls back to
   `ideal_target_description`/`strategic_thesis` free text if either is
   missing — never sends an empty query.
2. **Scrape a live Google Maps search page** — `firecrawl.scrape()` against
   `https://www.google.com/maps/search/<query>`, with a JSON extraction
   schema (`{businesses: [{name, address, category}]}`) plus the page's raw
   `links`. This pulls real, structured business listings straight off
   Google Maps for that search, not a generic web result.
3. **Match each business to its own listing URL** — Firecrawl returns the
   extracted JSON and the page's links uncorrelated, so `_match_place_link`
   regexes every link for a `/maps/place/<slug>/` segment and string-matches
   it against each business name, so "View Source" opens that specific
   listing rather than re-running the search.
4. **Return no web leads** if the Maps scrape throws or returns nothing. The
   existing low-scoring CRM result remains visible; arbitrary websites are
   never substituted for Maps listings.
5. **Never raises** — every exception at every step is caught and logged;
   a lead-finding fallback failing must never be the reason the whole
   match run fails.

## Worked example: Acme Capital

A full, real run of the matching pipeline end to end, showing the actual
data at every stage. The buyer is a fictional example, **Acme Capital**;
the flow and field names match the real code.

Trigger: a user runs `/find-match Acme Capital` in Slack (or picks "Acme
Capital" from the buyer-selection modal if the name is ambiguous).

### Stage 0 — Buyer context load

`BuyerRepository` loads the `buyer_roles` row for Acme Capital and maps it
into a `BuyerContext` value object. Only these fields are carried forward —
everything else on `buyer_roles` (`key_contact_attio_id`,
`acquisition_enrichment`, `deals_introduced`, `deals_converted`, `raw_attio`)
is not used by the pipeline today.

`BuyerResolutionService` then also fetches Acme Capital's recent free-text
meeting/call notes from the shared `meetings` table
(`MeetingRepository.get_recent_by_org`) and attaches them as
`meeting_notes` — a real conversation the team had, independent of anything
typed into the CRM's `notes`/`investment_strategy` fields.

```python
BuyerContext(
    buyer_role_id="8f2b...-uuid",
    org_attio_id="org_acme_capital",
    org_name="Acme Capital",
    model="Buy-and-build platform",
    mandate_status="Active",
    ebitda_floor=Money(amount=5_000_000, currency="USD"),
    check_size_min=Money(amount=20_000_000, currency="USD"),
    check_size_max=Money(amount=80_000_000, currency="USD"),
    ev_ceiling=Money(amount=150_000_000, currency="USD"),
    deal_structure_tolerance="Majority or full acquisition only",
    earnout_tolerance="Up to 20% of consideration",
    profitable_only=True,
    investment_strategy=(
        "We acquire profitable healthcare services businesses based in "
        "Saudi Arabia. We do not invest in fintech. Looking for founder-led "
        "operators with recurring revenue."
    ),
    notes="Met the principal at a Riyadh conference in March, strong appetite.",
    contact_person_id="ppl_12345",
    meeting_notes=[
        MeetingNote(
            occurred_at=datetime(2026, 8, 10, tzinfo=UTC),
            title="Follow-up call with Acme Capital",
            summary=(
                "Acme confirmed they specifically favor recurring-subscription "
                "operators over one-off project work, and are open to a "
                "minority growth-equity check first if the founding team "
                "stays on for at least 2 years."
            ),
            truncated=False,
        ),
    ],
)
```

### Stage 1 — Requirement extraction (Bedrock, one call)

`BuyerRequirementExtractionService` builds a prompt from `BuyerContext`: the
eight structured fields above go in as trusted "known fields",
`investment_strategy` + `notes` go in as free text for the LLM to mine, and
— when present — `meeting_notes` are rendered as a clearly labeled section
(`render_meeting_notes_section`, `app/shared/types/meeting_note.py`) and
appended after everything else. The label explicitly warns the note may
describe a *different* organization (a real risk: some meeting notes mix a
buyer's own thesis with mentions of other orgs' listings), and instructs the
LLM to fold anything derived only from a note into `strategic_thesis`/
`ideal_target_description` rather than invent a new structured criterion —
if it must become a `hard_requirement`/`soft_preference` anyway, it must use
`human_confirmed: false`. When `meeting_notes` is empty, this whole section
is omitted — the prompt is byte-identical to the no-notes case.

**Prompt sent to Bedrock (abbreviated):**

```
Extract structured buyer requirements as strict JSON matching this shape:
{hard_requirements: [...], soft_preferences: [...], strategic_thesis,
ideal_target_description, scoring_rubric, data_confidence}.
...
Organization: Acme Capital
Known structured buyer fields: {'model': 'Buy-and-build platform',
  'mandate_status': 'Active', 'ebitda_floor': Money(5,000,000 USD), ...}
Investment strategy (free text): We acquire profitable healthcare services
  businesses based in Saudi Arabia. We do not invest in fintech. Looking
  for founder-led operators with recurring revenue.
Notes (free text): Met the principal at a Riyadh conference in March,
  strong appetite.
Recent meeting notes (context only, not verified CRM data — may also
describe other organizations mentioned in conversation, not only Acme
Capital; never treat facts here as confirmed unless they also appear in
the structured fields above):
- [2026-08-10] Acme confirmed they specifically favor recurring-subscription
  operators over one-off project work, and are open to a minority
  growth-equity check first if the founding team stays on for at least 2
  years.
Any hard_requirement or soft_preference derived only from these meeting
notes must use source llm_extracted/llm_inferred and human_confirmed:
false — never crm_field/human_confirmed: true. Prefer folding meeting-note
content into strategic_thesis or ideal_target_description over minting a
new structured requirement from it at all.
```

**Bedrock's validated output → `RequirementProfile` (version 1 for this buyer):**

```python
RequirementProfile(
    hard_requirements=[
        HardRequirement(criterion="geography", value="Saudi Arabia",
                         source="llm_extracted", confidence="high",
                         human_confirmed=False),
        HardRequirement(criterion="industry", value="healthcare",
                         source="llm_extracted", confidence="high",
                         human_confirmed=False),
        HardRequirement(criterion="sector_exclusion", value="fintech",
                         source="llm_extracted", confidence="high",
                         human_confirmed=False),
        HardRequirement(criterion="profitable_only", value="True",
                         source="crm_field", confidence="high",
                         human_confirmed=True),
    ],
    soft_preferences=[
        SoftPreference(criterion="recurring_revenue_model", value="True",
                        weight=0.6, source="llm_extracted", confidence="medium"),
        SoftPreference(criterion="founder_led", value="True",
                        weight=0.4, source="llm_extracted", confidence="medium"),
    ],
    strategic_thesis="Buy-and-build consolidation of profitable, "
                     "founder-led healthcare operators in Saudi Arabia.",
    ideal_target_description="A profitable, recurring-revenue healthcare "
                              "services business in KSA, founder still "
                              "operating day-to-day.",
    scoring_rubric={"geography": 1.0, "industry": 1.0,
                    "recurring_revenue_model": 0.6, "founder_led": 0.4},
    data_confidence=0.72,
    generated_by_model="anthropic.claude-...",
    version=1,
)
```

Note: `profitable_only` came from a real CRM field, so it's
`source="crm_field"`, `human_confirmed=True` — it **can** eliminate a
candidate at Stage 1. The three requirements pulled from free text are
`llm_extracted`/`human_confirmed=False` — they influence scoring but cannot
eliminate anyone on their own until a human confirms them.

This profile is persisted immediately onto the run's header row in
`match_results` (`rank IS NULL`), so the run stays queryable even if
everything after this fails.

### Stage 2 — Candidate retrieval + Stage 1 structured filtering

`StructuredCandidateRetriever` loads all eligible sellers (Branch 1: plain
structured query, no vector search yet) — say 172 seller orgs — then
`apply_structured_filters` runs each hard requirement against each
candidate's populated fields (`geographic_focus`, `sector_focus`,
`est_ebitda`, etc.), using the seller equivalent of `SellerCandidate`.

Three example sellers survive to illustrate the next stage:

| Seller | HQ / geo focus | Sector focus | Profitable |
|---|---|---|---|
| HealthTrack MENA | KSA | Healthcare | Yes |
| Fintech Target Co | UAE | Fintech | Yes |
| PaySecure Holdings | UAE | Fintech | Yes |

Filter outcome:
- `geography = Saudi Arabia` → HealthTrack **Pass**, Fintech Target Co **Fail**, PaySecure **Fail**
- `industry = healthcare` → HealthTrack **Pass**, the other two **Fail**
- `sector_exclusion = fintech` → HealthTrack **Pass** (not fintech), Fintech Target Co **Fail** (is fintech, hard-eliminated), PaySecure **Fail** (is fintech, hard-eliminated)
- `profitable_only` (CRM-backed) → all three **Pass**

Because `geography`/`industry`/`sector_exclusion` are `llm_extracted`
(unconfirmed), Stage 1 does **not** eliminate on them alone unless the
mapped seller field is actually populated and contradicts the requirement —
which it is here, so all three fail structurally on multiple hard
requirements (see "Hard vs. soft requirements" above for the precise
elimination rule and table). In a case where a seller's `sector_focus` were
unpopulated, that criterion would be exempted (`filters_skipped`) rather
than silently failing the seller.

`candidates_considered=172`, `candidates_filtered=<passed count>` are
recorded on the run row.

### Stage 3 — Deterministic scoring (`ScoringEngine`)

Every hard requirement gets weight `1.0`; soft preferences use their
extracted `weight`. Each criterion produces `(result, data_backing,
sub_score)` via the same evaluator Stage 1 uses (`_evaluate_criterion`), so
filtering and scoring never disagree (see "Scoring rubric" above).

**HealthTrack MENA** (passed the filter):

```python
CandidateScore(
    overall_score=91.4,       # weighted average of sub-scores
    confidence=DataConfidence(value=100.0, applicable_criteria=4, total_criteria=6),
    criteria=[
        CriterionScore(criterion="geography", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="industry", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="sector_exclusion", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="profitable_only", result="Pass", data_backing="crm_field", weight=1.0),
        CriterionScore(criterion="recurring_revenue_model", result="Unknown", data_backing="unavailable", weight=0.6),
        CriterionScore(criterion="founder_led", result="Unknown", data_backing="unavailable", weight=0.4),
    ],
)
```

`data_confidence` reflects how much of the score is grounded in real CRM
data (`crm_field`), not match quality — it's a separate signal from
`overall_score`, deliberately not folded into ranking (§12/§14).

`select_top_n` ranks all scored, filter-surviving candidates by
`overall_score` descending and keeps the top 3 (`STAGE3_TOP_N`).

### Stage 4 — Reasoning (Bedrock, one call, narrative only)

`MatchReasoningService` sends the buyer's profile plus the shortlisted
candidates' deterministic scores/criteria (never raw documents, never
un-shortlisted sellers) and asks for narrative only — it cannot change the
score, cannot re-run the filter, cannot invent facts not given to it.

The buyer's `meeting_notes` are appended here too (same labeled section as
Stage 1), so the note about favoring recurring-subscription operators and a
minority-first structure can shape `recommended_pitch` even though it never
touched the deterministic score. Seller-side notes are on by default too
(`ENABLE_SELLER_MEETING_NOTES=true`) — notes for the *shortlisted* sellers
only (never all ~172 candidates) are fetched and added per-candidate to
`candidates_context` — narrative only, same "may describe another
organization" label, applied per seller this time since a seller's note
could just as easily mix in a different org's details. Set
`ENABLE_SELLER_MEETING_NOTES=false` to restrict enrichment to the buyer
side only.

**Output for HealthTrack MENA:**

```python
ReasoningResult.candidates[0] = {
    "seller_role_id": "...",
    "why_it_matches": (
        "HealthTrack MENA is the strongest match. Its sector_focus is "
        "confirmed Healthcare, directly aligning with Acme Capital's "
        "thesis. Its geographic_focus is KSA, precisely the target "
        "geography, and it is not in the excluded fintech sector."
    ),
    "why_chosen_over_alternatives": (
        "Ranked first because it is the only candidate to pass every hard "
        "requirement on real CRM data; the other two candidates are "
        "categorically excluded by both geography and sector."
    ),
    "recommended_pitch": (
        "Position Acme Capital's buy-and-build platform and its appetite "
        "for founder-led operators who want to keep running the business "
        "post-acquisition."
    ),
    "risks_and_gaps": (
        "Recurring-revenue mix and founder involvement are not yet "
        "confirmed in CRM data — verify directly before making an offer."
    ),
}
```

### Stage 5 — Persistence (one atomic transaction)

For each shortlisted candidate: a `match_scores` row (score breakdown +
reasoning text) is created first, then a `match_results` candidate row
(`rank`, `match_score`, `data_confidence`, the three narrative fields,
`status="PENDING_REVIEW"`) linked to it via `match_score_id`. The run's
header row is marked complete in the same transaction.

```
match_results (rank=1): HealthTrack MENA  — score 91.4, confidence 100, PENDING_REVIEW
match_results (rank=2): Fintech Target Co — score 17.0, confidence  67, PENDING_REVIEW
match_results (rank=3): PaySecure Holdings — score 17.0, confidence  67, PENDING_REVIEW
```

### Stage 6 — Slack delivery (and the web-fallback branch)

The background task (`match_dispatch.py`) posts a placeholder ("✨ *Finding
matches, please wait…*"), runs the full pipeline above (Stages 0-5 — this
always happens, even when every candidate ends up scoring low), then edits
that same message in place with the real result.

If every candidate scores below `WEB_FALLBACK_MIN_SCORE` (see "Web fallback
(Firecrawl)" above for the exact trigger condition), the placeholder is
updated again ("✨ *No match found, searching Google Maps for potential
sellers…*") and the Firecrawl leads are shown instead. Otherwise, the
normal result:

```
Buyer: Acme Capital
─────────────────────────────
1. HealthTrack MENA — 91/100
   Data confidence: 100/100
   HealthTrack MENA is the strongest match. Its sector_focus is confirmed
   Healthcare, directly aligning with Acme Capital's thesis...
   [View Full Analysis] [Approve Match] [Reject Match]

2. Fintech Target Co — 17/100
   Data confidence: 67/100
   Fintech Target Co does not meaningfully match Acme Capital's acquisition
   criteria — excluded fintech sector, wrong geography...
   [View Full Analysis] [Approve Match] [Reject Match]

3. PaySecure Holdings — 17/100
   Data confidence: 67/100
   ...
```

### Stage 7 — Approve / Reject

Clicking **Approve Match** on HealthTrack MENA re-validates the row against
the database (never trusts the Slack payload's claimed state), checks the
state-machine transition (`PENDING_REVIEW → APPROVED` is legal;
`APPROVED → *` is not), updates the row, then:

1. Posts an ephemeral confirmation: `Match with HealthTrack MENA approved by @you.`
2. Rebuilds the same message from persisted state and replaces the original
   in place — HealthTrack MENA's buttons are gone, replaced with:
   `✅ APPROVED by @you`, while the other two candidates still show their
   buttons (each is decided independently).

**View Full Analysis** posts an ephemeral message rendered entirely from the
already-persisted `MatchAnalysis` (run + candidates + scores) — it never
re-calls Bedrock, so it's instant and cheap, and always shows exactly what
was scored and reasoned, not a fresh (possibly different) re-run. Each
candidate header shows the seller's actual org name (`seller_org_name`,
resolved via the persisted `seller_organization` relationship, not the raw
`seller_attio_id`) and rounded whole-number scores — e.g. `PaySecure
Holdings — 53/100`, never a raw floating-point value.

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
