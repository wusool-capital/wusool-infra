# lead_magnets

The five lead-magnet tools — **Valuation**, **M&A Readiness**, **GCC SME
Benchmark**, the **Buyer Network** and **Get Started** — and the AI endpoints
behind them.
Replaces a Vercel + Render + Tally arrangement that called Anthropic
directly from the browser and wrote only to legacy Attio lists the Postgres
mirror does not read.

Not independently deployed: `server/main.py` registers this module's router
and static mount on the same FastAPI app as the Slack bot, served on a
second Caddy hostname pointing at the same container.

## Status

All eight endpoints serve, wired into `server/main.py`. `POST /benchmark`
and `POST /readiness/score` are verified over HTTP against a real Postgres
and live Bedrock. `POST /buyer/apply` and `POST /submit-lead` are built and
unit-tested but unverified against a real Attio/Postgres pair.

All five tools now serve (see `static/README.md`): benchmark, readiness
and valuation were ported from the live tools and repointed off their old
Render relays; buyers is a new page (no live tool existed — the network
only ever ran on Tally) at `/buyers/`, posting to `POST /buyer/apply`.
Get Started is the second Tally replacement, at `/get-started/`, posting to
`POST /get-started` — and the first tool embedded as a **modal** rather than
inline, because the CTA it replaces opens an overlay (see `static/README.md`).

## Structure

_New to this codebase's layering? See [the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

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
      email.py                     # confirmation + internal email content
      data/valuation.json          # 1000 M&A deals, 127 VC rounds, 31 comp sectors
    benchmark/
      benchmark.py                 # the percentile engine + js_round
      benchmark_dataset.py         # generated peer dataset; do not hand-edit
      benchmark_submission.py      # one submission end to end: ratios, score, implied EV
      benchmark_routing.py         # internal triage: priority, reason, quality gates
      benchmark_narrative.py       # which metrics earn a paragraph, and how it is filled
      benchmark_copy.py            # generated report prose; do not hand-edit
      email.py                     # confirmation + internal email content
    readiness/
      readiness.py                 # the questionnaire, advisory rules, band map (pure)
      email.py                     # confirmation + internal email content
    buyer_network/
      buyer_network.py             # org type / sector focus / target geography validation
      email.py                     # confirmation + internal email content
    get_started/
      get_started.py               # sell_timeline option validation
      email.py                     # confirmation + internal email content
    shared/                        # used by 2+ tools — see the note above
      dedup.py                     # normalisation + key composition (pure)
      tool_run.py                  # the ledger's own vocabulary (Tool, Stage, …)
      attio_values.py              # tool result -> Attio attribute values
      email_content.py             # shared HTML shell + formatting for the two emails
      prompts.py                   # every prompt, as a pure function
      sector_mapping.py            # tool sector -> sector_focus; raises on unmapped
      sector_options.py            # the live 85 option titles; generated
      search.py                    # the search-result domain type
      schemas.py                   # pydantic models for tool_runs.payload — see below
  application/
    valuation/
      valuation_ai.py               # enrich, analyze, compare
    shared/
      base.py                       # ServiceBase — composes Pipelines + SubmissionService
      service.py                    # LeadMagnetService — the one facade bootstrap.py builds
      submit.py                     # the write contract, every tool goes through it
      pipelines.py                  # per-tool dispatch from the stored payload
      email_dispatch.py             # per-tool email content dispatch, mirrors pipelines.py
      sweeper.py                    # resumes abandoned runs
      ports/                        # one Protocol per file: llm, search, attio, tool_runs
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
    get_started/endpoints.py        # /get-started
  tests/
```

`application/shared/base.py` + `service.py` compose by construction, not
the multiple-inheritance mixin split the guide above describes for `crm`:
`Pipelines` and `SubmissionService` take genuinely different Ports and are
deliberately tested standalone (`test_valuation_ai.py` builds a bare
`Pipelines`; `test_submit.py` injects fake `run_ai`/`fallback` callables
into a bare `SubmissionService`), so mixing them into shared-state sibling
concerns would force every pipeline-only or submission-only test to fake
Ports it has no use for. `bootstrap.build_submission_service` now returns
one `LeadMagnetService` instead of wiring the two by hand.

`domain/shared/schemas.py` is this module's one deliberate exception to
"no pydantic in `domain/`/`application/`" — `tests/test_architecture.py`
allowlists `pydantic` for exactly that one file path, nothing else. Four
families of type live there:

- **Stored-payload models** (`BenchmarkPayload`, `ReadinessPayload`,
  `ValuationPayload`, `BuyerNetworkPayload`, `AttioIdentityPayload`) type
  `tool_runs.payload`, one per tool, mirroring the corresponding
  `api/schemas.py` request. `pipelines.py` parses it with
  `SomePayload.model_validate(payload)` instead of `payload.get(key)` plus a
  manual `isinstance` check per field — `bootstrap.py::_RoleAttioWriter.write`
  does the same, via the smaller `AttioIdentityPayload` (domain, company
  name, sector) since it reads a different subset of fields than any one
  tool's own pipeline model does. Deliberately permissive (`extra="ignore"`,
  no re-declared `ge`/`le`/length constraints): the data was already
  strictly validated once at the API boundary, and the stored dict also
  picks up the write contract's own bookkeeping keys later (`stage`, `ai`,
  `attio`, readiness's `score`) that these models were never meant to
  reject.
- **Bedrock response models** (`EnrichResult`, `AnalyzeResult`,
  `SearchQueries`, `CompareResult`, `ReadinessResult`, `InternalNote`) are
  what `LeadLLMPort`'s seven methods actually return — moved here from
  `providers/bedrock/schemas.py` so `application/` can see the real model
  (a `dict` used to cross that seam) without importing `providers/`: both
  sides depend inward on `domain/`, neither imports the other. Strict, no
  `extra="ignore"` — they match exactly what each prompt's forced tool-call
  schema asks Bedrock for.
- **`attio_values.py` input models** (`ReadinessValuesInput`,
  `BuyerValuesInput`) bundle what `readiness_values()`/`buyer_values()`
  used to take as several loose keyword arguments into one validated
  object. `benchmark_values()`/`valuation_values()` keep their domain
  dataclass argument(s) as-is — already the right type, wrapping it again
  would be ceremony, not safety. `valuation_values(result, inputs, *,
  consent=...)` takes the raw `ValuationInputs` alongside the computed
  `Valuation` so the visitor's own numbers (revenue, EBITDA, owner salary,
  stage, consent) reach Attio too, not just the blended range.
- **Generated report-copy models** (`FlagCopy`) — the benchmark report's
  client-facing paragraphs, quoted verbatim from the live tool. Pure data
  with no behaviour, so it lives here rather than as a plain dataclass.

Closed string vocabularies elsewhere in `domain/` are `StrEnum`s, not
`pydantic`, since a `str`-typed member needs no validation and every
existing `dict[str, str]`/plain-`str` consumer keeps working unchanged
against them: `benchmark.py`'s `MetricKey`/`PercentileColumn`,
`readiness.py`'s `QuestionId`/`RevenueRange`, and `sector_options.py`'s
`SectorFocus` (the 85 live `sector_focus` option titles — every value in
`sector_mapping.py`'s four mapping tables references one of its members).

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
| `POST /get-started` | serves | No model at all — pure seller lead capture; the form's own figures go straight to `seller_role` |
| `POST /submit-lead` | serves | No model call at all — the blended valuation is entirely deterministic, computed inline from the visitor's `/compare` comps and `/analyze` discounts, DCF overrides and search terms |
| `GET /reports/{slug}` | serves | Gated insights report: the free part for a new reader, the whole report for a returning one |
| `POST /reports/{slug}/unlock` | serves | The report gate (name, email, optional organisation); emails a 6-digit code through SES and returns a `challenge_id`. Records nothing |
| `POST /reports/{slug}/unlock/verify` | serves | Takes `{challenge_id, code}`. On a match it returns the whole report and records the reader. A wrong code is 400; an expired, used-up or unknown code is 410 |
| `GET /reports/{slug}/pdf` | serves | The whole report as an A4 PDF, printed per download; 403 until the reader unlocks |
| `POST /reports/webhooks/sanity` | serves | Signed Sanity publish webhook for both document types; syncs the Webflow Reports card or Insights article |

`/enrich`, `/analyze` and `/compare` are stateless: they build the report the
visitor reads while still in the tool, long before there is a submission to
record. `/analyze` and `/compare` are meant to run in parallel — the split is
what makes the preview ready when the loading screen ends.

All four ledger-backed endpoints (`/benchmark`, `/readiness/score`,
`/buyer/apply`, `/get-started`) commit the ledger row **before** responding, not at
dependency teardown. Two reasons, both load-bearing: the contract is that
the lead is durable before the visitor is told anything, and the background
completion opens its own session, so an uncommitted row is invisible to it.

## Gated insights reports (PRD 3)

The business publishes a report in the Sanity Studio (`sanity/` at the repo
root). The report then appears at `wusoolcapital.com/reports/<slug>` with
its free part open and the rest behind one short form. There are three parts:

- **Content.** `providers/sanity/report_source.py` reads the published report
  over GROQ and caches it, misses included, for 5 minutes per process. The
  cache holds at most 512 slugs, and page views have their own per-IP limit
  (`LEAD_MAGNET_REPORT_READS_PER_HOUR`), so slug-scanning can't drain the
  Free quota. The
  Free-plan dataset is public, which is an accepted risk described in
  `sanity/README.md`.
- **Flattening.** Some exports draw their pages with JavaScript. "Buyouts in
  the GCC" is a self-unpacking design-tool bundle whose 40 A4 pages and
  React tables exist only after its scripts run. On each publish,
  `application/insights_report/sync.py` opens a new HTML version once in
  headless Chromium (`providers/chromium/renderer.py`, network blocked, one
  render at a time, capped at 30 s) and saves the drawn page back to
  Sanity's hidden `renderedHtml`, plus where the free preview ends
  (`renderedPreviewEnd`), so readers never re-split. Readers are served only
  that copy; an unrendered report is a 404. The save is guarded by the
  document revision it read, so an older render that finishes late is
  dropped. The playbook renders in about 2.4 s and peaks at about 300 MB RAM.
  Hidden copies (`<template>`, `<noscript>`, `[hidden]`) are removed so
  they can't leak into the preview.
- **Rich text reports.** Editors can write a report in the Studio instead of
  pasting HTML. `providers/sanity/portable_text.py::rich_report` turns it into
  a styled page (title, DM Sans, A4 print margins) and marks the gate at the
  editor's `lockedPercent` of the text (75% locked by default), since it has
  no pages, and never after the last block; the serializer keeps a mark it finds. From there it follows the pasted path: render, gate, save, PDF.
- **Gate.** `domain/insights_report/split.py` cuts between block elements,
  never at an inline tag. A paged export is cut after the editor's `freePages`
  (1 by default, never the last page), an export without pages after its
  first block, and a rich report at its own mark. `freePages` is part of the
  render fingerprint, so changing it re-renders. `GET /reports/{slug}` never sends the
  rest to a new reader.
  - `POST /reports/{slug}/unlock` emails a one-time code
    (`application/insights_report/unlock.py`). Nothing reaches `tool_runs`
    or Attio yet, so a mistyped address never becomes a lead.
  - A code lasts `LEAD_MAGNET_REPORT_CODE_TTL_S` (10 min) and allows five
    guesses. One inbox gets three codes per 10 minutes; `+tags` and Gmail
    dots count as the same inbox.
  - `LEAD_MAGNET_REPORT_EMAIL_OTP=false` turns the code off: `/unlock`
    then records the reader and returns the whole report, as before.
  - Pending codes live in process memory, because only one container runs.
    A deploy drops codes in flight, and those readers request a new one.
  - `POST /reports/{slug}/unlock/verify` with the right code records an
    `insights_report` run through the write contract, returns the whole
    report, and sets the `wusool_reader` cookie, which holds the run id.
  - A returning reader skips the form.
  - Their first visit to a *different* report records one more run, keyed
    `<reader>:<slug>`, so every report read becomes one `activities` row
    for PRD 2.
  - `GET /reports/{slug}/pdf` prints the stored `renderedHtml` to A4 on
    each download, under the same Chromium lock, network block and 30 s cap
    as the render; a download still queued at 30 s is a 503. Google Fonts
    are the one exception to the block: the server fetches them from a fixed
    host list and hands them to Chromium. It returns 403 without a reader
    cookie, has its own per-IP budget (`LEAD_MAGNET_REPORT_DOWNLOADS_PER_HOUR`),
    and records a run on another report's cookie the same way a page view does.
- **Card.** `application/insights_report/sync.py`, triggered by the Sanity
  webhook, creates or updates the item in the Webflow Reports collection.
  The webhook replies 202 at once and syncs in the background, so Sanity
  never times out and retries mid-sync. A failed sync is only logged
  (`insights_report_sync_failed`); republishing the report repairs it.
  Signatures older than 10 minutes are rejected as replays.
  Cards go live without a Publish in Webflow. A new card uses the live
  create; an existing one is written to its staged item, then published, since
  the live update 409s on a card an earlier sync unpublished.
  - One pin, `bannerPinned` -> Webflow `pin-to-banner` (home page bar), is
    level-triggered. Every sync writes the report's own tick. The sync always
    writes the card's `featured` off; the top of `/reports` is the newest card.
  - Taking the pin unticks it on the other reports in Sanity (drafts included,
    release versions left alone) and Webflow, only after this card is live.
    Sanity goes first, in one transaction. Each loser's own
    webhook then repairs a Webflow unpin that failed. Reports are matched by
    document id, so this report's own draft is never unticked, even with a
    renamed slug.
  - Only reports last edited no later than this one are unticked, so the
    later of two simultaneous pins wins. Each untick's own webhook re-syncs
    that report.
  - The server never refills an empty pin: the banner list shows nothing.
    The `/reports` featured block sorts **Featured** on first, then newest,
    with a limit of 1, so it shows the newest report.

CRM write: the `insights_report` branch of `bootstrap._RoleAttioWriter`
writes an **organisation and a person only**, with no role and no deal.
`AttioRoleWriter.write_organization` links an existing org without patching
it. The org domain comes from the reader's email unless the address is
free-mail. The organisation is optional: when it is blank, only the person
is written, and a failure raises so the sweeper retries it. No emails are sent (`email_dispatch.sends_emails`). The
"Insights & Reports" option must exist on `lead_source_detail` in Attio
before this ships.

Who read which report, and when: every reader's first access to each report
is one `tool_runs` row, with the report in its payload and the time in
`started_at`. Repeat visits to the same report aren't recorded again.

```sql
SELECT started_at, payload->>'report_title' AS report, payload->>'slug' AS slug,
       payload->>'name' AS name, payload->>'email' AS email, payload->>'company' AS company
FROM tool_runs WHERE tool = 'insights_report' ORDER BY started_at DESC;
```

## Insights articles from Sanity

The Studio's second type, `insights`, publishes ordinary (ungated) articles to
the Webflow Insights collection. The same Sanity webhook carries it; the
endpoint routes on the projected `type`.

- **Content.** `providers/sanity/article_source.py` reads the article fresh
  from the API host. Editors pick rich text or pasted HTML per article.
  `providers/sanity/portable_text.py` turns Portable Text into the HTML
  hand-written articles use, and passes every body through `nh3` with a tag
  allow-list. This matters: Webflow's API stores script tags and
  `javascript:` links verbatim (checked 2026-10-07).
- **Item.** `application/insights_article/sync.py` creates, updates or
  unpublishes the item via `providers/webflow/insights_cms.py`. Items it
  creates carry `sanity-managed`; it never updates or unpublishes one
  without it, so a slug clash with a hand-written article is skipped and
  logged (`insights_article_sync_skipped_unmanaged`). It never writes
  `hide-from-listings` or `gated`. Content type, silo and author are
  resolved to Webflow ids by name; an unknown content type fails the sync.
- **Pin.** `featured` is the one field shared with hand-written items. A
  pinned article unticks other Sanity articles (raw perspective, drafts
  included, later pin wins) with the write token, then clears `featured` on
  every other live item. Each unticked article's own webhook rewrites its
  item, so a failed Webflow step still heals. Like the report banner, it never refills an empty
  pin: the featured block's own sort shows the newest article.
- **Plumbing.** `providers/webflow/collection.py` holds the Webflow API code
  both providers share: live create, staged update then publish, unpublish,
  and option lookups.

## The write contract

The order is the whole point; it is what makes a lost lead impossible.

1. **Record the submission** — `tool_runs.start(...)`, before any AI or
   Attio call.
2. **Respond to the browser.** Nothing that fails after this can lose the
   lead.
3. **AI work.** Valuation and Benchmark fall back to their own
   deterministic calculations. Readiness has none by decision, which is
   precisely why step 1 exists.
4. **Write to Attio**, `is_test` always set. One `organizations` record,
   one `seller_role` entry (with its `sector`) or one `buyer_role` entry
   **per ticked sector** (`target_vertical`, found again by vertical on a
   resubmission; the form's sectors no longer land on the organisation),
   one `person`, and one `deal` at
   stage **Inbound** so the lead lands in the pipeline rather than waiting
   for someone to key it in by hand.
5. **Email the visitor** a confirmation, via SES (`domain/<tool>/email.py`
   builds the HTML, `notifications.EmailSenderPort` sends it).
6. **Email the internal team** a notice, with links back to the Attio
   organisation/deal (`SubjectRefs.org_web_url`/`deal_web_url`).
7. **`tool_runs.finish(...)`**, then one `activities` row joined by
   `tool_run_id`.
8. A **sweeper** replays anything left unfinished.

Steps 5 and 6 are tracked as two separate stages (`email_confirmation`,
`email_internal`), not one — a resume after step 6 fails must not re-send
the visitor's confirmation, which already landed. Either stage is skipped
permanently (not retried) when there is no visitor address or no
`LEAD_MAGNET_EMAIL_FROM`/`LEAD_MAGNET_EMAIL_TO` configured — a config gap
the sweeper re-attempting on a timer cannot fix, and the lead is already
safe in Attio regardless of whether these emails go out.

Postgres is never written directly for entity data: the Attio→Postgres
webhook mirror in `ddl_commands` already maps every lead-magnet and
benchmark column, so this module writes Attio and lets the mirror follow.

### No dedup, no blocking — every attempt keeps its own row

`tool_runs` is an append-only attempt log. `start()`
(`persistence/tool_runs_repository.py`) never rejects a submission. A
visitor can resubmit any number of times, for any tool, and each genuinely
new attempt gets its own permanent `tool_runs` row and (once it resolves a
subject) its own `activities` row with a full copy of that attempt's
payload. Nothing is overwritten.

The one exception: an exact retried POST of the very same request (an
identical `submission_id` already recorded for this client) reuses that
row rather than starting a second one — a plain network-level retry, not a
new visit. Without this, every retry would reprocess the whole pipeline:
a second Attio write, a second visitor confirmation email, a second
internal-team notice, and (for readiness, whose scoring call sits on the
response path rather than the background pipeline) a second billed
Bedrock call.

`idempotency_key` (`email|domain`) tags each row with which client it
belongs to — it carries no tool name, and is **not** unique, so a
genuinely new submission is never blocked or merged into an older row; it
is only used to narrow the exact-retry lookup above.

"One row per client/organisation" is enforced one layer up instead, at the
CRM level, unaffected by any of this:
- **Organisation**: matched by domain+name (`bootstrap.py::_find_existing_org`),
  and every match gets its Attio fields patched with the latest submitted
  values.
- **Person**: matched by email (`providers/attio/person_writer.py`) —
  deliberately fills blanks only and never overwrites a matched contact's
  `name`, to protect hand-curated data.

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
`promote_role_fks()` fills those in later. `buyer_role_id` is the first
vertical's role; `buyer_role_entry_ids` lists every role the submission made,
as Attio entry ids, since no Postgres row exists yet to point at.

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
- `deals` — not touched at all. The `deal` record is written to Attio and
  the `ddl_commands` webhook mirror (`sync_deal`) lands the Postgres row.
- `person` — a stub insert (`attio_id`, `name`) `ON CONFLICT DO NOTHING`,
  so `tool_runs.person_attio_id` has something to point at until the mirror
  lands the full record. `providers/attio/person_writer.py` is what now
  populates that id (a real Attio `person` create/patch), same shape as
  `AttioRoleWriter` for organisations — `ddl_commands` still owns the
  Postgres side of `person` (raw SQL in `persistence/attio_sync.py`), this
  module still only seeds the stub `finish()` always seeded.

### Deal dedupe — one per organisation, not per submission

A company that runs the valuation tool and then the benchmark is one inbound
lead, not two. `providers/attio/deal_writer.py` queries `deal` before
creating (same query-then-create shape, and the same reason, as the person
write below), and returns a matched deal **untouched** — its stage is a
human's working state, and a later lead magnet must never drag a `Qualified`
deal back to `Inbound`.

The match against `seller_id`/`buyer_id` happens client-side: `entries.py`'s
own opening docstring already documents that this codebase has no verified
filter syntax for a record-reference attribute, so `find_deals_by_party`
pages every `deal` instead of trusting a guessed filter body — the same
trade `resolve_role_entry_id` makes for `parent_record_id`, and cheap at
this scale for the same reason.

Which side the submitting organisation goes in follows the tool: the three
seller tools write `seller_id` + `deal_type: Sell-side`; `buyer_network` is
an acquirer applying to the network, so it writes `buyer_id` + `Buy-side`.

`deal_owner` is always set, from `LEAD_MAGNET_DEAL_OWNER_ID`. Attio does not
mark the attribute required, but every deal in the live workspace has an
owner, so an unowned one would be the only unassigned card in the pipeline.
A create Attio *rejects* is retried once with
`LEAD_MAGNET_DEAL_OWNER_FALLBACK_ID`: the primary advisor leaving the
workspace would otherwise silently stop every lead-magnet deal from being
created, visible only as a log line, since this write is best-effort.

`deal_value` is deliberately never written. No `Inbound` deal in the live
workspace carries one — value is set by a human as the deal advances, and a
self-reported figure from the valuation tool is not that.

`SubjectRefs.deal_attio_id` is deliberately **not** a `tool_runs` column,
unlike the four subject ids next to it. It is only ever read back out of
`payload.attio`, which is what makes a sweeper resume skip the deal write —
no migration, and a row stored before the field existed simply defaults it.

### Person dedupe — why not an upsert

`person.email` on this workspace is a plain **text** attribute, single-valued
and **not unique** — not Attio's standard multi-valued `email_addresses`
type. That rules out an atomic `PUT ?matching_attribute=` upsert entirely:
the dedupe is a `POST /objects/person/records/query` filtering `email`
(case-insensitive on this attribute), sorted by `created_at` so a retry
always resolves the same person, then filtered client-side on `is_test` —
same reason as `resolve_role_entry_id`: Attio's checkbox filter has no "is
empty", so a server-side filter would silently miss a pre-migration record
and create an unwanted duplicate.

**Fill-blanks-only on a match, never overwrite.** `company`/`linkedin`/`phone`
are patched only when the matched record's own value for that attribute is
currently empty; `name` is never touched on a match at all. A lead magnet
can only ever add a `company`/`linkedin`/`phone` a hand-curated contact
never had, never relabel one that is already there. If a match already has
everything filled in, nothing is written.

**Best-effort.** A person-write failure is logged and swallowed
(`bootstrap.py::_RoleAttioWriter._with_person`) — the org/role write has
already landed by that point, and this module's sweeper would otherwise
re-enter the whole write on a retry, risking a duplicate organisation (see
"The subject-FK ordering trap" above). The email is already durable in
`tool_runs.payload` before any Attio call runs, so a person-write failure
never loses the lead, only a CRM convenience:
```sql
SELECT id, tool FROM tool_runs
WHERE status = 'succeeded' AND person_attio_id IS NULL
  AND coalesce(payload->>'email', '') <> '';
```

## Not built yet

- Gated reports verified live. Not yet checked:
  - that a live-API Webflow item shows on `/reports` without a site
    publish;
  - the first-page cut against the real "Buyouts in the GCC" playbook.

- `POST /buyer/apply` and `POST /submit-lead` verified against a real
  Attio/Postgres pair — both built and unit-tested, but never exercised
  end to end the way `/benchmark` and `/readiness/score` have been.

## Testing

`domain/shared/dedup.py` carries the densest unit coverage in the module: it is
pure, and a normalisation bug silently merges or splits real companies.
`tests/test_architecture.py` enforces that `domain/`/`application/` never
import `persistence/`/`providers/`/`api/`/`fastapi`/`pydantic`/`sqlalchemy`.
