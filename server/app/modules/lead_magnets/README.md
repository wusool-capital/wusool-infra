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

All seven endpoints serve, wired into `server/main.py`. `POST /benchmark`
and `POST /readiness/score` are verified over HTTP against a real Postgres
and live Bedrock. `POST /buyer/apply` and `POST /submit-lead` are built and
unit-tested but unverified against a real Attio/Postgres pair, and every
endpoint is gated behind the front end, which does not exist yet
(`static/` is still empty) — so nothing can reach any of them in
production.

The tool pages are not served yet: `static/` is still empty.

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

Layered `domain → application → persistence → providers → api`
(enforced by `tests/test_architecture.py`), and inside `domain/` and
`application/` grouped a second way, by tool. A file used by exactly one
tool lives in that tool's own subpackage; a file two or more tools depend
on — the ledger vocabulary, the write contract, the Bedrock/Attio clients —
lives in `shared/` instead. `persistence/` and `providers/` stay flat: they
are one ledger and one set of clients for every tool, not four.

```
lead_magnets/
  config.py                     # Settings — see "Env var names" below
  domain/
    valuation/
      valuation.py                 # sector resolution, peer matching, stats
      valuation_data.py            # typed loaders over data/valuation.json
      valuation_methods.py         # DCF + 3 comps methods + the blend (the fallback)
      strategic_analysis.py        # /analyze's deterministic pros/cons/insights fallback
      data/valuation.json          # 1000 M&A deals, 127 VC rounds, 31 comp sectors
    benchmark/
      benchmark.py                 # the percentile engine + js_round
      benchmark_dataset.py         # generated peer dataset; do not hand-edit
      benchmark_submission.py      # one submission end to end: ratios, score, implied EV
      benchmark_routing.py         # internal triage: priority, reason, quality gates
      benchmark_narrative.py       # which metrics earn a paragraph, and how it is filled
      benchmark_copy.py            # generated report prose; do not hand-edit
    readiness/
      readiness.py                 # the questionnaire, advisory rules, band map (pure)
    buyer_network/
      buyer_network.py             # org type / sector focus / target geography validation
    shared/                        # used by 2+ tools — see the note above
      dedup.py                     # normalisation + key composition (pure)
      tool_run.py                  # the ledger's own vocabulary (Tool, Stage, …)
      attio_values.py              # tool result -> Attio attribute values
      prompts.py                   # every prompt, as a pure function
      sector_mapping.py            # tool sector -> sector_focus; raises on unmapped
      sector_options.py            # the live 85 option titles; generated
      search.py                    # the search-result domain type
  application/
    valuation/
      valuation_ai.py               # enrich, analyze, compare
    shared/
      submit.py                     # the write contract, every tool goes through it
      pipelines.py                  # per-tool dispatch from the stored payload
      sweeper.py                    # resumes abandoned runs
      ports/                        # every Protocol, one file
  persistence/
    database.py                    # sessionmaker bound to this module's DATABASE_URL
    mappers.py                      # tool_runs row -> ToolRunRecord; where the ORM type stops
    tool_runs_repository.py         # the write-ahead ledger — one, for every tool
  providers/
    bedrock/ firecrawl/ attio/
  api/
    router.py, schemas.py, dependencies.py, static.py   # shared
    valuation/endpoints.py          # /enrich /analyze /compare /submit-lead
    benchmark/endpoints.py          # /benchmark
    readiness/endpoints.py          # /readiness/score
    buyer_network/endpoints.py      # /buyer/apply
  tests/
```

## Endpoints

Paths follow the migration spec's own table, not this module's invention.
`/benchmark` additionally keeps the path the live benchmark page already
posts to, so repointing it is a host change rather than a path change.

| | | |
|---|---|---|
| `POST /benchmark` | serves | No model at all — scored against the peer dataset |
| `POST /readiness/score` | serves | Sonnet 4.6, no fallback by decision |
| `POST /enrich` | serves | Sonnet 4.6 over a Firecrawl scrape of the one known URL |
| `POST /analyze` | serves | Sonnet 4.6; sector judgement, discounts, DCF overrides, strategic read, scorecard — falls back to a deterministic pros/cons/insights on failure |
| `POST /compare` | serves | Haiku plans queries, Firecrawl runs them, Sonnet selects; shortfall filled from static data |
| `POST /buyer/apply` | serves | No blocking model call; a best-effort Haiku qualification note, never shown to the applicant |
| `POST /submit-lead` | serves | No model call at all — the blended valuation is entirely deterministic, computed inline |

`/enrich`, `/analyze` and `/compare` are stateless: they build the report the
visitor reads while still in the tool, long before there is a submission to
record. `/analyze` and `/compare` are meant to run in parallel — the split is
what makes the preview ready when the loading screen ends.

All three ledger-backed endpoints (`/benchmark`, `/readiness/score`,
`/buyer/apply`) commit the ledger row **before** responding, not at
dependency teardown. Two reasons, both load-bearing: the contract is that
the lead is durable before the visitor is told anything, and the background
completion opens its own session, so an uncommitted row is invisible to it.

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

## Sector mapping

Every tool asks for a sector in its own vocabulary and none matches the
CRM's. Two rules make a silent loss impossible: every target is validated
against the live 85 `sector_focus` options **at import**, and an unmapped
input **raises** rather than defaulting to "Diversified / Generalist" — a
wrong sector misfiles the lead and skews any sector report built on it,
which is worse than a missing one.

All 31 of the benchmark tool's dropdown values are mapped, with the compound
"Supply Chain or mobility" split so mobility keeps its own target (both are
live options, so nothing needed creating in Attio). The pre-split label
still maps, so a submission from the current form does not raise before the
form ships the two separate options.

**Fully mapped now.** All three tools' vocabularies resolve:
`BENCHMARK_SECTORS` (31), `READINESS_SECTORS` (11), and
`VALUATION_SECTORS` (204 of the valuation tool's 225-label `ALL_SECTORS`
— the other 21 already resolved by exact string match or by reusing
`BENCHMARK_SECTORS`). Valuation's own vocabulary is not free text: the
visitor sees the same 225 as a `<select>`, same mechanism as readiness's,
and `/enrich`/`/analyze` also see the same list.

204 fine-grained VC/startup labels against an 85-option CRM taxonomy means
several targets are real judgment calls, not obvious 1:1 matches —
flagged in `_VALUATION_SECTORS_FOR_REVIEW` (15 entries) rather than one
comment per line, the same way "DeepTech or hardware" and
"F&B & Hospitality" are flagged individually. Worth a second look from
someone with sector-taxonomy context before treated as settled.
`UNMAPPED_VOCABULARIES` is empty now; `to_sector_focus` still raises
rather than defaulting on anything genuinely new.

## Still to port

- **Valuation.** Ported: the datasets, the pure helpers, the DCF, the
  four-method blend, `generateStrategicAnalysis` (`/analyze`'s
  deterministic pros/cons/insights fallback), and all four AI/write
  endpoints (`/enrich`, `/analyze`, `/compare`, `/submit-lead`). Nothing
  from the live valuation tool remains unported.
- The live tool turned out to make only **two** AI calls, not the six the
  handover documents describe: the enrichment call and one analyst
  mega-prompt covering eight steps. `callClaude` is defined and never
  called. The five-prompt count came from counting steps and `web_search`
  uses.
- **Benchmark.** Ported and verified. What remains is only the Attio field
  mapping (`relay-benchmark.js`'s ~40 slugs, its live-schema read and
  slug-remap handling) — a `providers/attio/` concern, not domain logic.
- `sector_mapping.py` and its test, with the mobility split applied
  (42 mappings): the benchmark tool's compound `"Supply Chain or mobility"`
  option becomes `"Supply Chain"` → `Supply Chain / Distribution` and
  `"Mobility"` → `Mobility`, both live `sector_focus` options.
- The Buyer Network, which exists in neither repo — it is a Tally form today
  and the only tool being built rather than moved.
- End-to-end Firecrawl verification — the only unproven half of the
  comparables pipeline.

## Currency: settled

The handover documents contradicted each other on this, and it was the
highest-risk open question — a wrong answer is wrong by 3.6725x with nothing
in the data to show it. Resolved from the source, three independent ways:

1. `wusool-benchmark.html`'s band cuts are USD (`Under USD 545k`, max
   `545000`), with the comment "the original AED 2m / 10m / 30m cuts
   converted at 3.6725". 2,000,000 / 3.6725 = 544,860.
2. The same file states it outright: *"The engine computes in USD in both
   modes. The toggle governs entry and display only."* `toCalc` divides AED
   input by the peg on the way in.
3. `toUSD`, the function feeding the Attio write, is a round-only no-op —
   *"Already USD, so this only rounds."*

So **every destination is USD** and the `_aed` suffix on the benchmark
list's Attio attributes is a misnomer; the live code even names a local
`rentAed` while assigning a USD figure to it. The `toAed()` deletion applies
to valuation and readiness (via `index.js`) only — benchmark already stores
USD and needs nothing removed.

`benchmark-dataset.json` in the source repo is a **stale pre-conversion
copy** and must not be ported from: it declares `"currency": "AED"`, has the
AED band cuts, and its `revEmp` anchors are the peg larger.

## How the ports are verified

Not by hand-computed expectations. Each ported engine was run against its
original by extracting the JavaScript into a node harness and diffing over a
generated grid:

| Ported | Reference cases | Mismatches |
|---|---|---|
| `benchmark.py` percentile engine | 6,860 | 0 |
| `benchmark_routing.py` route + quality | 6,840 | 0 |
| `benchmark_submission.py` full `compute` | 8,019 | 0 |
| `valuation.py` stats, matching, benchmarks | 350 | 1 (see below) |
| `valuation_methods.py` DCF, comps, blend | 3,000 | 0 outside Qatar |

That is what caught `js_round`. JavaScript's `Math.round` rounds a half away
from zero and Python's `round` rounds a half to even, so `round(42.5)` is 42
here and 43 in the browser — 79 of the 8,019 cases differed by exactly one
point. A benchmark score off by a point from the report a visitor already
downloaded is a real discrepancy, so `js_round` is used for every rounded
figure and pinned by a test.

The committed tests keep the branches that would regress silently rather
than the whole grid.

### The one intentional divergence

`tax_rate("Qatar")` and `tax_rate("Bahrain")` return **0**, where the live
tool returns 20. It propagates: 270 of the 3,000 DCF reference cases differ,
and only the Qatar ones. Measured on those, the bug moved the blended
mid-point by up to 63% for a profitable business (understated, because the
tax drag was invented) and up to 31% the other way for a loss-making one
(overstated, because a 20% rate softened negative cash flow with a tax
shield that does not exist). Neither direction was visible in the output. Its lookup reads `return t[geo] || 20` and JavaScript
treats `0` as falsy, so two jurisdictions whose table entries are correctly
`0` are silently taxed at 20% — inflating the tax drag in the DCF and
undervaluing every Qatari and Bahraini business. Reproducing that
bug-for-bug would mean knowingly under-valuing real companies, so the port
returns the table's own figure and a test pins the difference.

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

- The front end. `static/` holds only a README; nothing can reach any of
  the seven endpoints in production until it exists.
- The `activities` timeline row (step 6 — it needs a resolved subject, so
  it cannot be written before the Attio write succeeds).
- `POST /buyer/apply` and `POST /submit-lead` verified against a real
  Attio/Postgres pair — both built and unit-tested, but never exercised
  end to end the way `/benchmark` and `/readiness/score` have been.

## Testing

`domain/shared/dedup.py` carries the densest unit coverage in the module: it is
pure, and a normalisation bug silently merges or splits real companies.
`tests/test_architecture.py` enforces that `domain/`/`application/` never
import `persistence/`/`providers/`/`api/`/`fastapi`/`pydantic`/`sqlalchemy`.
