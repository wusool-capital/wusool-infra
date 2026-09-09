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
  persistence/
    database.py               # sessionmaker bound to this module's DATABASE_URL
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

## Blocked on

- The four tool files and `index.js`, currently in `dopamine-relay` /
  `wusool-benchmark` (private, personal account). Needed for the prompts,
  the deterministic fallbacks, the static pages and `embed.js`.
- `sector_mapping.py` and its test, with the mobility split applied
  (42 mappings): the benchmark tool's compound `"Supply Chain or mobility"`
  option becomes `"Supply Chain"` → `Supply Chain / Distribution` and
  `"Mobility"` → `Mobility`, both live `sector_focus` options.
- End-to-end Firecrawl verification — the only unproven half of the
  comparables pipeline.

## Testing

`domain/dedup.py` carries the densest unit coverage in the module: it is
pure, and a normalisation bug silently merges or splits real companies.
`tests/test_architecture.py` enforces that `domain/`/`application/` never
import `persistence/`/`providers/`/`api/`/`fastapi`/`pydantic`/`sqlalchemy`.
