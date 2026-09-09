# lead_magnets

The four lead-magnet tools — **Valuation**, **M&A Readiness**, **GCC SME
Benchmark** and the **Buyer Network** — and the AI endpoints behind them.
Replaces a Vercel + Render + Tally arrangement that called Anthropic
directly from the browser and wrote only to legacy Attio lists the Postgres
mirror does not read.

Not independently deployed: `server/main.py` registers this module's router
and static mount on the same FastAPI app as the Slack bot, served on a
second Caddy hostname pointing at the same container.

## Status

Partial. The pure and persistence layers are in place; the endpoints, the
prompts and the tool pages are blocked on inputs that live outside this
repo — see "Blocked on" below.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

```
lead_magnets/
  config.py                # Settings — see "Env var names" below
  domain/
    dedup.py                  # normalisation + key composition (pure)
    readiness.py              # the questionnaire, advisory rules, band map (pure)
    prompts.py                # every prompt, as a pure function
  persistence/
    database.py               # sessionmaker bound to this module's DATABASE_URL
    mappers.py                # tool_runs row -> ToolRunRecord; where the ORM type stops
    tool_runs_repository.py   # the write-ahead ledger
  application/ports/          # every Protocol, one file
  providers/
    bedrock/ firecrawl/ attio/
  tests/
```

## The write contract

The order is the whole point; it is what makes a lost lead impossible.

1. **Record the submission** — `tool_runs.start(...)`, before any AI or
   Attio call.
2. **Respond to the browser.** Nothing that fails after this can lose the
   lead.
3. **AI work.** Valuation and Benchmark fall back to their own
   deterministic calculations. Readiness has none by decision, which is
   precisely why step 1 exists.
4. **Write to Attio**, `is_test` always set.
5. **`tool_runs.finish(...)`**, then one `activities` row joined by
   `tool_run_id`.
6. A **sweeper** replays anything left unfinished.

Postgres is never written directly for entity data: the Attio→Postgres
webhook mirror in `ddl_commands` already maps every lead-magnet and
benchmark column, so this module writes Attio and lets the mirror follow.

### Why `tool_runs` and not `activities`

`activities` carries `CHECK (subject_attio_id IS NOT NULL OR subject_uuid IS
NOT NULL)`, so a submission that dies before its Attio write cannot be
recorded there at all — exactly the lead-loss case this exists to catch.
`tool_runs` has four nullable subject columns and no such constraint,
deliberately.

### The subject-FK ordering trap

`tool_runs.organization_attio_id` and `person_attio_id` are foreign keys
into Postgres `organizations`/`person`, but at step 5 those rows exist only
in **Attio** — the mirror lands them seconds later. Setting them naively
FK-violates on every genuinely new lead. `finish()` therefore seeds both
parent rows `ON CONFLICT DO NOTHING` (the mirror's own upsert overwrites the
stub), and resolves `seller_role_id`/`buyer_role_id` through a
`legacy_entry_id` subquery that is simply NULL until the mirror has run.
`promote_role_fks()` fills those in later.

## Three rules that fail silently if broken

- **Send USD, convert nothing.** Every destination is USD;
  `utilities.domain.Money` types `currency` as `Literal["USD"]` and raises
  on anything else. Two of the four tools convert to AED on the way in
  today — the fix is deleting that conversion, not adding a second one.
  Getting it wrong is wrong by 3.67× with nothing in the data to show it.
- **Always set `is_test`.** One Attio workspace serves both environments.
  A record written without the flag is invisible in *both* views — Attio's
  checkbox filter has no "is empty", so it does not default to production,
  it disappears.
- **Attio first, Postgres second.** A nightly job overwrites Postgres from
  Attio, so anything written straight to Postgres is destroyed on the next
  run.

## Env var names

Module root `Settings` classes read **unprefixed** env vars, and
`server/.env.example` is one flat file, so two modules declaring the same
field name silently share one value — the same collision the Terraform
stacks hit with `instance_type`. Everything specific to these tools is
therefore `LEAD_MAGNET_*`; only genuinely shared values use bare names
(`DATABASE_URL`, `AWS_REGION`, `FIRECRAWL_API_KEY`).

No AWS key setting exists. Bedrock is reached through the instance's IAM
role, so there is nowhere for a key to live — which is the point.

## Source of the ported logic

- `github.com/ramzy0z/dopamine-relay` — **public**, not private as the
  handover document said. Holds `dopamine-valuation.html`,
  `dopamine-readiness-score.html` and `index.js` (the relay backend).
- `github.com/wusool-capital/wusool-benchmark` — private, org-owned. Holds
  `wusool-benchmark.html`, `relay-benchmark.js`, `benchmark-dataset.json`
  and `attio-setup.js`.

Anything ported from either is quoted verbatim where the value is a
contract — an Attio option title, a text field a human reads, a JSON key the
page parses. `tests/unit/test_readiness.py` is the regression net for that.

## Still to port

- **Valuation.** Five prompts (`dopamine-valuation.html` around lines 401,
  1430, 2247, 2417, 2594, 2877), the `DAMODARAN_WACC` table and industry
  growth benchmarks (~811-1243), and the auto-DCF module (~1632+) — the last
  of those is the deterministic fallback, so the visitor still gets a real
  valuation when the model fails. Two of its prompts use Anthropic's
  `web_search` tool, which is what the Firecrawl pipeline replaces.
- **Benchmark.** `relay-benchmark.js` (its Attio field names and scoring) and
  `benchmark-dataset.json` (the peer dataset it scores against — no AI
  involved in its output at all).
- `sector_mapping.py` and its test, with the mobility split applied
  (42 mappings): the benchmark tool's compound `"Supply Chain or mobility"`
  option becomes `"Supply Chain"` → `Supply Chain / Distribution` and
  `"Mobility"` → `Mobility`, both live `sector_focus` options.
- The Buyer Network, which exists in neither repo — it is a Tally form today
  and the only tool being built rather than moved.
- End-to-end Firecrawl verification — the only unproven half of the
  comparables pipeline.

## Defects confirmed in the live source

Read from the two repos above, not inferred:

- `index.js:179` rejects a submission with a blank domain outright
  (`400 domain is required`), and `dopamine-readiness-score.html`'s
  `pushReadinessToAttio` returns early on the same condition. A lead with no
  website is lost twice over.
- `pushReadinessToAttio` is called with the model's own result, so the Attio
  write only happens **after** the AI call succeeds. That is the live
  lead-loss path this module's step 1 exists to close.
- `index.js` assigns `advisoryNote = ai.internalAdvisoryNote || null`,
  discarding the deterministic note wholesale — so a "DEAL RISK … do not
  refer" flag disappears whenever the model's prose does not repeat it.
  `merge_advisory` is the fix.
- Both tools pin outdated models: `claude-sonnet-4-20250514` (readiness) and
  a `web_search_20260209` tool version in valuation.

## Table ownership

This module owns `tool_runs`. It also touches three tables it does not own,
each deliberately:

- `organizations` — through `app.modules.organizations`'
  `OrganizationRepository.create`, which is already
  `ON CONFLICT DO NOTHING` and documents this exact webhook race.
- `seller_roles` / `buyer_roles` — read only, as a `legacy_entry_id`
  subquery resolving this module's own foreign keys. No role data is read or
  written.
- `person` — a stub insert (`attio_id`, `name`) `ON CONFLICT DO NOTHING`,
  so `tool_runs.person_attio_id` has something to point at until the mirror
  lands the full record. **This one is a known wart:** `ddl_commands` owns
  `person` and writes it with raw SQL in `persistence/attio_sync.py`, but
  exposes no repository or facade for it, so there is nothing to go through.
  The alternative — adding a person facade to `ddl_commands` — is a larger
  change than this module should be making. Worth revisiting if a second
  caller ever needs the same stub.

## Not built yet

- `bootstrap.py`. There is no wiring to centralise until the endpoints
  exist; `api/dependencies.py` currently constructs nothing but a session.
  When the endpoints land, concrete provider and repository construction
  belongs there, not in `dependencies.py`.
- `api/router.py`, `api/schemas.py` and the five endpoints; `domain/prompts.py`,
  `domain/mapping.py`; `providers/attio/role_writer.py`; the `activities`
  timeline row (step 6 — it needs a resolved subject, so it cannot be
  written before the Attio write succeeds).

## Testing

`domain/dedup.py` carries the densest unit coverage in the module: it is
pure, and a normalisation bug silently merges or splits real companies.
`tests/test_architecture.py` enforces that `domain/`/`application/` never
import `persistence/`/`providers/`/`api/`/`fastapi`/`pydantic`/`sqlalchemy`.
