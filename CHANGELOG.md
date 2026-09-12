# Changelog

Meaningful changes to `wusool-infra` — infrastructure, the Wusool Toolkit
Slack bot, and the Attio ↔ PostgreSQL data platform.

The project has no version tags: every merge to `dev` / `prod` deploys.
Entries are grouped by date, newest first, using the
[Keep a Changelog](https://keepachangelog.com/) categories. For the current
delivered state and outstanding items see
[`docs/handover/README.md`](docs/handover/README.md).

## 2026-09-12

### Added

- Each Wusool Toolkit user-guide page (`/find-match`, `/edit-seller`/
  `/edit-buyer`, `/add-seller`/`/add-buyer`, `/enrich-seller`/
  `/enrich-buyer`) now includes a worked example walkthrough — a real
  command, the bot's actual response text, and the concrete next step —
  using one consistent example buyer/seller pair (Raoof Capital, Al Noor
  Manufacturing) across all four pages so they read as one coherent
  journey. Also corrected several stale references to the per-candidate
  "Enrich" button on match results and after `/add-seller` (both replaced
  with `/enrich-seller`/`/enrich-buyer` hint text earlier today) that the
  docs hadn't caught up to.

### Changed

- `/add-*` and `/edit-*` now offer **HQ country** and **Region** as
  multi-selects instead of free-text boxes. Both stay `text` in Attio and
  Postgres — the picked titles are joined with `", "`, the same
  `multi_select_as_text` shape `client_type` already uses, so no migration
  and no Attio schema change. HQ country carries a 97-country subset (Slack
  caps a multi-select at 100 options), weighted to GCC/MENA and the major
  financial centres; a country outside it still renders as an editable
  free-text box. Titles are .NET `RegionInfo.EnglishName` spellings, matching
  what the SOURCE migration wrote into the column.

### Fixed

- **A `multi_select_as_text` field was silently cleared whenever its stored
  value fell outside the picker's vocabulary.** `multi_select_block` falls
  back to a free-text box in that case, but extraction only ever read
  `selected_options` — so the box submitted as `None` and wiped the column on
  the next save of *any* field on that record. Affected `client_type` in
  production; would have hit every out-of-vocabulary `hq_country`.
- Matching's geography criterion compared a buyer's target against the whole
  of `organizations.hq_country`, so an org headquartered in more than one
  country scored `Fail` on every geography match. It now compares per value.
- Discovery's Google Maps client now logs the query, businesses found, and
  how many got a resolved place link (vs. falling back to the shared
  search URL) on every successful run — previously the only log lines
  fired on failure or when an exclusion removed something, so a clean run
  that still surfaced a wrong/mismatched lead (e.g. a "View on Maps" link
  pointing at an unrelated search) left zero diagnosable trace.
- **`enrichment`'s and `lead_magnets`' Firecrawl `search()` clients were
  silently discarding every single result, every time, regardless of query
  quality.** Both read `url`/`title`/`description` directly off the SDK's
  `Document` object — confirmed live against a real account that these are
  never populated at the top level; they only ever live on
  `item.metadata` (a `DocumentMetadata`). `enrichment`'s client filtered
  out any result with no `url`, which meant it discarded 100% of results
  100% of the time (`"No new field values found from public sources"` on
  every `/enrich-buyer`/`/enrich-seller` call, no matter how well-anchored
  the query was — confirmed live: a properly domain/sector-anchored query
  for Mubadala Investment Company still returned 0 documents until this
  fix, then 5, including its own site and Wikipedia).
  `lead_magnets`' client didn't filter, so it silently returned results
  with empty `title`/`url`/`snippet` instead of failing outright. Both
  clients (and their tests, which mirrored the same wrong assumption) now
  read from `item.metadata` first, falling back to the top-level
  attributes only if a future response shape ever populates them.
  Discovery's Maps client is unaffected — it extracts into its own JSON
  schema (`MapsExtraction`), not raw `Document` attributes.

### Changed

- `/enrich-buyer`/`/enrich-seller`'s Firecrawl research query is no longer a
  bare `"{name} company profile"` — it now anchors on the organization's own
  domain when known, else enriches with sector/category/HQ country. The
  extraction prompt is also grounded with a "what we already know" block so
  the LLM can reject sources about a different, same-named company. Fixes a
  live case where `/enrich-buyer Investcorp` returned nothing because the
  generic query surfaced only one thin, unrelated snippet.
- Discovery's lead search ("Find more sellers" / the automatic
  below-threshold trigger) now uses more of a buyer's requirement profile,
  not just `sector`/`geography`: `client_type` is folded into the search
  query as a refining qualifier (e.g. "healthcare SMB"), and every
  `sector_exclusion` value is collected and used to filter out any
  discovered lead whose category/name matches it — Google Maps' own search
  has no dependable negation syntax, so this filtering happens after the
  search, before the result limit is applied. Revenue/EBITDA floors and
  CRM-internal states (`outreach_tier`, `relationship_status`,
  `appetite_signal`) are deliberately still not used — a Maps listing
  carries no financial data, and those fields describe a seller's state in
  our own CRM, meaningless for a lead that isn't in the CRM yet.

### Fixed

- Diffbot's `logo_url`/`linkedin`/etc. proposed values in an enrichment
  review message now render as a short clickable link instead of dumping
  the full raw (often encoded) URL as text.
- A match result's "Enrich" button is replaced with a `/enrich-seller
  <name>` hint — freeing the `enrich_seller_from_match` action id
  exclusively for the seller-add flow's own "Enrich" button.
- The enrichment proposal message no longer shows the always-empty
  `Current:` line or a low-value `source` link — `propose()` only ever
  proposes a value for a field that was already missing.
- `client_type`/`last_attempt_channel`/`target_geography` FieldSpecs
  corrected to match live SOURCE Attio (verified directly against the real
  workspace): SOURCE's `client_type` converted to `text` on 2026-08-31 (our
  code was still built against a select-typed workspace), a stale
  "WhatsApp" option removed from `last_attempt_channel`, and `Egypt`/
  `Global` added to `target_geography`.
- Two real test-isolation bugs: `full_resync`'s e2e test now explicitly
  opts out of the `ATTIO_IS_TEST` prod-only guard it's exercising, and a
  different `full_resync` unit test was silently performing a real,
  unmocked database write (via `_sync_streaming_entity`), leaking a stub
  organization row that broke an unrelated e2e test depending on run order.
- `lead_magnets`' rate limiter is now reset between tests — it previously
  leaked global state across the test session, causing a spurious 429 on
  an unrelated later test depending on run order.
- People Data Labs' `founded` year is now guarded the same way Diffbot's
  founding-date parsing already was — an out-of-range value used to crash
  the entire enrichment proposal (including any good fields Diffbot had
  already resolved) instead of just dropping that one field.
- Diffbot's `est_revenue` is no longer proposed when its `currency` isn't
  USD (or unset) — the write path and extraction prompt both hardcode USD
  with no FX conversion anywhere in the pipeline, so a foreign-currency
  figure was silently written as if it were USD.
- Discovery's `discover_add_seller` button handler now catches a decode
  failure on a stale/legacy button value — it used to be an uncaught,
  silent no-op after `ack()`, with only a server-side stack trace and no
  message to the operator.

### Changed

- The Bedrock retry/logging scaffolding around `retry_with_backoff`
  (`enrichment`'s and `lead_magnets`' clients carried a byte-identical
  copy) is now one shared `invoke_bedrock_with_retry`
  (`utilities.providers.bedrock.retry`) — `matching_engine`'s own,
  differently-shaped hand-rolled loop is left as-is, per that module's own
  documented reasoning.
- Every Slack handler module used to construct its own
  `InProcessTaskRunner()`/`InMemoryIdempotencyStore()`, fragmenting
  in-flight background-task and idempotency state across six separate
  instances. Both are now process-wide singletons
  (`utilities.get_shared_task_runner()`/`get_shared_idempotency_store()`) —
  every idempotency key was already prefixed by its own command/action
  name, so sharing carries no collision risk.
- `RoleReaderPort.current_values`/`company_context` merged into one
  `load()` method — both already read the same role+organization row, so
  the split cost a genuine extra database round trip on every
  research-tier enrichment call rather than just being a style choice.
- Each discovered lead in the "Find more sellers" result now shows a "View
  on Maps" button alongside "Add as seller", so an operator can sanity-check
  the actual listing before adding it — `DiscoveredLead.source_url` was
  already captured but previously unused for display. Two buttons per lead
  needs an `ActionsBlock`, not a `SectionBlock` accessory (Slack allows only
  one accessory per section).

### Fixed (from merge-check)

- Diffbot's non-USD `est_revenue` skip and discovery's exclude-term lead
  filtering now both log why (`diffbot_est_revenue_skipped_non_usd`,
  `discovery_leads_excluded`) — previously silent, correct but
  undiagnosable from logs alone.

### Fixed (from live testing)

- Discovery's free-text fallback search query (used when a buyer's
  `RequirementProfile` lacks a clean `sector`/`geography`) and the
  `client_type` fold added earlier today are now capped to a short phrase
  before reaching Google Maps — an uncapped multi-clause description
  produced a query Maps couldn't resolve at all ("can't find [the whole
  sentence]"). Confirmed via comparison against `origin/prod`'s deleted
  `web_search.py` that the query-construction code itself was unchanged
  from prod; the underlying weakness was always there, just invisible on
  prod, which silently dropped an empty search result instead of always
  posting one.
- `_match_place_link`'s regex required a trailing slash after a Google Maps
  place-link slug, rejecting two real link shapes (no trailing slash, or a
  trailing `?query` string) and silently falling every such lead back to
  the shared, unresolved search URL — the direct cause of "View on Maps"
  opening the same failed search for every lead in a batch instead of that
  lead's own listing.
- Diffbot's schemeless `linkedin`/`facebook` values (e.g.
  `"linkedin.com/company/acme"`, no `https://` prefix) now render as a
  clickable link the same way an `http(s)://`-prefixed value already did.
  A proposed value is also no longer wrapped in `*...*` bold markup at
  all — Slack's bold markup doesn't reliably apply either around its own
  auto-linkified text (a bare domain) or across a multi-line value (a long
  `description`); both showed up as literal asterisk characters instead of
  being interpreted as bold (confirmed live, both cases).
- The seller-add confirmation message's "Enrich" button is replaced with a
  `/enrich-seller <name>` hint, matching the match-result message's
  existing pattern. This was the only remaining UI surface emitting
  `enrich_seller_from_match`, so the now-fully-dead
  `handle_enrich_seller_from_match` handler and its only-real-caller-gone
  `_enrich_and_notify` glue function are removed with it.

## 2026-09-11

### Added

- Seller enrichment now tries two structured company-data providers before
  falling back to Firecrawl+Bedrock: Diffbot (`DIFFBOT_API_KEY`, 10,000
  free credits/month), then People Data Labs (`PEOPLE_DATA_LABS_API_KEY`,
  100 free lookups/month) for whatever Diffbot missed. Both optional; a
  directly-typed field from either provider's own database is treated as
  high-confidence and never re-researched via the LLM path. Buyer targets
  never call either provider — none of `BUYER_ENRICHABLE_FIELDS` are fields
  their schemas track. Diffbot's response shape is now verified live (see
  the Fixed entry below); People Data Labs' is not yet — confirm
  `providers/people_data_labs/schemas.py` against a real account before
  relying on it.
- `/toolkit-help` and `/toolkit-status` — answered directly in `main.py`
  rather than any one module, since no single module owns the full
  command list or knows the bot's overall health. `/toolkit-help` lists
  every registered command with its usage hint; `/toolkit-status` reports
  uptime, database reachability, and whether this instance is writing to
  Attio in test or production mode. (`/status` was the first name tried —
  Slack reserves that word and refused to register it; `/help` was
  renamed to match.)

### Changed

- `enrichment`'s review step no longer posts one "Accept & Save" button per
  proposed field with its own immediate write — it now shows every proposed
  field with a single "Review & Save" button that opens the real, prefilled
  `/edit-seller`/`/edit-buyer` modal (`EnrichmentReviewPort`, replacing
  `RoleUpdaterPort`); the write goes through that existing modal's ordinary
  submission path, not a bespoke one. Reachable from `/enrich-seller`/
  `/enrich-buyer`, the buyer "enrich first?" checkbox, and a new
  per-candidate "Enrich" button on each `/find-match` result.
- `discovery` no longer runs its own dedupe check before handing a lead to
  `ddl_commands` — `ddl_commands`' own `/add-seller` search
  (`organization_selection_modal`, including its existing "already has a
  seller role, use `/edit-seller` instead" message) is now the only dedupe
  in that pipeline. `discovery` lost its `DedupeMixin`/`OrganizationLookupPort`
  and its database connection entirely — it no longer touches Postgres.
- `organization_selection_modal`'s "existing org, no active role"
  branch now carries `discovery`'s prefill through to the resulting add
  form (it previously dropped it silently — the only branch that did).
- `/enrich-seller <name>` and `/enrich-buyer <name>` — the only enrichment
  commands; there is no bare `/enrich`, so an org with both an active
  buyer and seller role never needs a role-selection modal just to pick
  the kind.
- Buyer saves now suggest re-matching: every successful `/edit-buyer`
  confirmation appends a copy-pasteable `` `/find-match {org_name}` ``
  line. Replaces the old "enrich this buyer first?" checkbox on the
  `/find-match` buyer-confirmation modal, which stopped short of actually
  running the match — the checkbox is gone; the modal now shows a static
  tip pointing at `/enrich-buyer` instead.
- New sellers get an "Enrich" button too: `/add-seller`'s confirmation
  message now carries the same `enrich_seller_from_match` button a match
  result shows, reusing `matching_engine`'s existing handler via the
  shared action_id convention — no new handler, no cross-module import.

### Fixed

- Diffbot's Enhance API lookup was broken end-to-end, only caught by
  testing live against a real `DIFFBOT_API_KEY` account: the request used
  a DQL-style `query` param (`type:Organization name:"X"`), but the
  Enhance API wants `type`/`name` as separate params and 400s otherwise.
  Once fixed, the response also didn't match the schema —
  `foundingDate`/`revenue` are nested objects, not bare scalars, and
  `location.country` is itself an entity with its own `name` — none of
  which matched Diffbot's published docs, which this schema was
  originally written against blind. Also wired up `nbLocations`, `logo`,
  `angellistUri`, `facebookUri`, `twitterUri` — present on every Enhance
  response but previously unmapped despite matching existing
  `location_count`/`logo_url`/`angellist`/`facebook`/`twitter` columns.
- `enrichment`'s `enrichment_role_selection_modal` view submission had no
  duplicate-delivery guard, unlike its sibling view-submission handlers
  (`matching_engine`'s `buyer_selection_modal`) — a redelivered Slack
  submission would have spawned two background research runs (real
  Bedrock/Firecrawl/Diffbot/PDL cost) and posted two duplicate proposal
  messages. Added the same `InMemoryIdempotencyStore` pattern, keyed on
  the view id.

### Changed

- `providers/attio/role_writer.py`'s `write_seller_role`/`write_buyer_role`
  deduplicated: both were ~50 lines identical in structure (create-or-patch
  the organization with dedup-scope checking, then resolve-or-create the
  role-list entry), differing only in what goes into `org_values`, which
  list slug, and which `SubjectRefs` field gets set. Extracted into two
  private helpers, `_upsert_organization`/`_upsert_role_entry`, called by
  both public methods — kept inside `role_writer.py` rather than moved to
  `utilities`, since this is Attio-write business logic tied to this
  module's own `SubjectRefs`/list constants, not a generic cross-module
  primitive. No existing test exercised `AttioRoleWriter` directly (only
  a fake, at the `_RoleAttioWriter`/`bootstrap.py` layer above it), so
  verified live against the real dev Attio workspace instead, calling the
  refactored class directly to exercise all four branches: create and
  patch, for both seller and buyer roles. The patch calls returned the
  same `org_attio_id`/role-entry id (no duplicate created) and the raw v2
  API confirmed the patched fields actually changed
  (`benchmark_score` 61→77, `check_size_min/max` updated) — not just the
  same ids with stale data. All test records deleted afterward.

### Fixed

- Pre-merge `/code-review` over the full PR diff (not just this session's
  latest commits) surfaced four real bugs, all fixed and regression-tested:
  - **Every tech-mode GCC Benchmark submission's Attio write failed.**
    `bootstrap.py::_RoleAttioWriter.write` passed `peer_key` as the CRM
    sector for every benchmark submission — correct in SME mode (`peer_key`
    *is* the sector there), but tech mode's `peer_key` is a funding stage
    (`"seed"`, `"seriesa"`, ...), and the actual tech sector the form
    correctly collects (`static/benchmark/60-render.js`'s `S.inputs.sector`,
    repopulated from `DATA.techSectorList` in tech mode) was never sent to
    the backend at all. `to_sector_focus("seed")` raised
    `UnmappedSectorError` on every one, deterministically, so no tech-mode
    benchmark lead's organization/seller_role record ever reached Attio.
    Fixed at all three points: `BenchmarkRequest` gets a new `sector`
    field (`api/schemas.py`), the tech-mode form now sends it
    (`static/benchmark/60-render.js`), and `_RoleAttioWriter.write`
    resolves `seller.sector or seller.peer_key` (was `peer_key or
    sector`) so the real sector wins when present. Two new tests in
    `test_bootstrap.py` pin both the tech-mode and SME-mode paths.
  - **`promote_role_fks` never promoted anything.** It read
    `ToolRun.payload[key]` at the top level, but `set_stage(stage="attio",
    output=asdict(subjects))` nests `SubjectRefs` under
    `payload["attio"][key]` — the backfill query matched zero rows on
    every real submission, permanently leaving `seller_role_id`/
    `buyer_role_id` NULL whenever the Attio→Postgres mirror landed the
    role row after `finish()` (the common case, since the mirror lands
    "seconds after" per the method's own docstring). The one integration
    test covering this seeded an unrealistic top-level payload shape that
    happened to mask the bug; rewritten to go through the real
    `set_stage` path, and confirmed (by temporarily reverting the fix)
    that it now genuinely catches the regression.
  - **Attio and Postgres could disagree on a money amount.** This
    session's earlier fix rounded `serialize_money`'s Attio write to 2
    decimal places but left the sibling `to_postgres_money` — called with
    the exact same raw value by `write_payload.py`'s
    `build_postgres_values`/`build_attio_values` — unrounded, breaking
    `to_postgres_money`'s own documented "can never disagree" invariant
    for any amount with more than 2 decimal places (routine for a blended
    valuation figure). `to_postgres_money` now rounds identically. New
    `test_attio_and_postgres_round_a_blended_figure_the_same_way`.
  - **`extract_json` could raise instead of returning `{}`.** Its own
    docstring promises "`{}` on total failure rather than raising", but it
    indexed `response["output"]["message"]["content"]` with no guard — a
    response missing that shape raised a bare `KeyError` that bypasses
    every caller's `except BedrockInvocationError` handling, including
    `lead_magnets/application/shared/submit.py::complete`'s documented
    "never raises" contract. The identical bug already exists on `dev` in
    `meetings/providers/bedrock/client.py::_extract_json` (confirmed via
    `git show`) — pre-existing, not a regression from this PR's "moved
    verbatim" extraction into `utilities/domain/bedrock.py`. Fixed only in
    the new `utilities/` location, which `lead_magnets` depends on
    directly; `meetings`'/`matching_engine`'s own still-buggy copies are
    unrelated files, deliberately left untouched. New
    `test_returns_empty_dict_rather_than_raising_on_a_malformed_response`.
  - Six lower-severity maintainability/DRY observations from the same
    review (role_writer.py's seller/buyer duplication, two hand-maintained
    Attio option-set copies in `buyer_network.py`, a fallback-tool list
    encoded in three places, `AttioIdentityPayload`'s intentional overlap
    with the per-tool payload models) were evaluated and left as-is —
    pre-existing patterns, not regressions, correctly lower priority than
    the four correctness/data-integrity fixes above per this repo's
    `merge-check` skill's stated priority order. One (`organizations.type`
    carrying both "Roll-up" and "Roll") is an already-documented, live
    Attio workspace data-quality stray, not a code defect.
  - Verified: `checks.sh quality` and `checks.sh unit` both clean; the
    real `checks.sh integration` invocation (all four modules' integration
    suites together) passes except one pre-existing, unrelated
    `ddl_commands` test polluted by this session's own hours of manual
    live-Attio testing against a non-disposable local dev database — not
    a code defect, confirmed by isolating the test and reading its
    "organizations count mismatch" failure.

### Changed

- Two more raw-JSON seams in `lead_magnets` converted to Pydantic, found by
  a sweep for remaining `JsonObject`/untyped-dict usage:
  - `/analyze` (`api/valuation/endpoints.py`) had no `response_model` — a
    client generated from `/openapi.json` would have typed it `unknown`,
    the one endpoint of five not fully typed on the wire. Added
    `AnalyzeResponse` (`api/schemas.py`), every field but `pros`/`cons`/
    `insights` optional since `ValuationAi.analyze` genuinely returns a
    partial shape on a Bedrock failure (its deterministic fallback). New
    `test_analyze_response_model_accepts_both_the_full_and_fallback_shape`
    pins both real shapes against it.
  - `bootstrap.py::_RoleAttioWriter.write` — the concrete `AttioWriterPort`
    composition-root implementation — read `payload.get("domain")`,
    `payload.get("company") or payload.get("company_name")`,
    `payload.get("peer_key") or payload.get("sector")`, and hand-filtered
    `org_type`/`sector_focus` with `isinstance(v, str)`, independently of
    `pipelines.py`'s already-existing per-tool payload models. Now parses
    through those same stored-payload models: a new, smaller
    `AttioIdentityPayload` (domain, company, peer_key, sector) for the
    benchmark/valuation/readiness branch — a separate model rather than
    added fields on `BenchmarkPayload` etc., since none of those exist to
    serve this call site — and the existing `BuyerNetworkPayload` (now with
    a `domain` field) for the buyer branch. One real behaviour change: a
    non-string `org_type`/`sector_focus` entry in a stored payload now
    raises instead of being silently dropped, matching this module's
    established "raise rather than default" rule
    (`UnmappedSectorError`) — pinned by a new
    `test_write_rejects_a_non_string_org_type_entry`. Every real request
    already validates these as `list[str]` at the API boundary before
    storage, so this cannot fire on any live path, only a corrupted row.
  - Left deliberately untouched: `AttioWriterPort`/`ToolRunsPort`'s
    `payload`/`ai` (genuinely tool-agnostic — `submit.py` and the sweeper
    must work identically regardless of which tool's shape they're
    carrying), `attio_values.py`'s `dict[str, object]` return (already a
    generic Attio attribute-slug bag, the same shape the rest of the
    codebase uses for Attio writes), and `valuation_data.py`'s private
    `_raw()` loader (every public accessor already converts its result
    into a typed frozen dataclass one line later; wrapping the loader
    itself would just validate a static shipped file twice for no gain).

- Four closed string vocabularies in `lead_magnets/domain/` converted to
  `StrEnum`s so a typo fails at definition time instead of silently
  producing a dead dict entry or a missing lookup:
  - `benchmark.py`'s `MetricKey` (the nine `ebitda`/`growth`/`revEmp`/…
    scoring metrics) and `PercentileColumn` (the nine `seller_roles`
    `pct_*` columns each metric writes to), used at `PERCENTILE_COLUMNS`'
    and `benchmark_copy.py`'s definition sites only — not retrofitted into
    `benchmark_dataset.py`'s generated peer-cut tables or
    `benchmark_submission.py`/`benchmark_routing.py`'s existing
    string-keyed lookups, which stay untouched. In the same pass,
    `PercentileColumn.CONC` was corrected to `pct_concentration` (not
    `pct_revenue_concentration`, which does not exist), matching what was
    already verified against the live Attio workspace earlier.
  - `readiness.py`'s `QuestionId` (`q1`..`q13`, keying `QUESTION_OPTIONS`
    and `QUESTION_TEXT`) and `RevenueRange` (the five revenue bands
    `_REVENUE_MIDPOINT_USD` looks up).
  - `sector_options.py`'s `SectorFocus` (all 85 live `sector_focus`
    option titles, replacing a bare `frozenset[str]`) and every value
    across `sector_mapping.py`'s four mapping tables (`_BENCHMARK_SME`,
    `_BENCHMARK_TECH`, `READINESS_SECTORS`, `VALUATION_SECTORS` — 248
    targets in total) now reference `SectorFocus.X` instead of a raw
    string literal. `SECTOR_FOCUS_OPTIONS` stays a `frozenset[str]` over
    the enum's members, so `buyer_network.py` and the existing tests that
    do `value in SECTOR_FOCUS_OPTIONS` needed no changes — every
    `StrEnum` member is a `str`.
  - `benchmark_copy.py`'s `FlagCopy` (the client-facing report paragraphs)
    moved from a plain frozen dataclass in `benchmark_narrative.py` into
    `domain/shared/schemas.py` as a Pydantic model — pure data with no
    behaviour, so it now lives with everything else that shape.
  - Verified: `ruff check .`, `ruff format --check .`, `ty check .`, and
    the full non-integration `pytest` suite (691 passed) all clean.

- Extended `domain/shared/schemas.py`'s pydantic exception to the two
  remaining raw-JSON seams in the module:
  - **`LeadLLMPort`'s seven methods now return real Pydantic models**
    (`EnrichResult`, `AnalyzeResult`, `SearchQueries`, `CompareResult`,
    `ReadinessResult`, `InternalNote`×2) instead of a plain `dict`. These
    moved from `providers/bedrock/schemas.py` (deleted) into `domain/
    shared/schemas.py`, since `application/` still can't import
    `providers/` — both layers can import `domain/`, so that's the one
    place they can share a type without either depending on the other.
    `LeadBedrockClient._invoke` no longer calls `.model_dump()` before
    returning. Every consumer updated to attribute access:
    `pipelines.py`'s `_readiness`/`_buyer_network`,
    `valuation_ai.py`'s `enrich`/`analyze`/`compare` (the last of which
    now returns a new `ComparablesResult` instead of a hand-built dict,
    removing the `isinstance(q, str)`/`isinstance(c, dict)` filtering that
    existed only because the old contract was untyped), and both
    `api/readiness/endpoints.py` and `api/valuation/endpoints.py`'s
    `/enrich`/`/compare` handlers. `readiness/endpoints.py`'s
    `_store_score` now takes a `ReadinessResult` and calls `.model_dump()`
    itself at the one point a plain dict is actually needed (the raw SQL
    JSONB merge); `pipelines.py`'s resume path re-hydrates it back via
    `ReadinessResult.model_validate(stored_score)`.
  - **`attio_values.py`'s `readiness_values()`/`buyer_values()`** now take
    one bundled `ReadinessValuesInput`/`BuyerValuesInput` model instead of
    several loose keyword arguments. `benchmark_values()`/
    `valuation_values()` were left as-is — they already take one
    well-typed domain dataclass, which wrapping again would not improve.
  - Verified live against the real dev Attio workspace: all seven
    `LeadLLMPort` operations exercised with real Bedrock calls
    (`/enrich`, `/analyze`, `/compare`, `/readiness/score` — including its
    resume/background-completion path — and `/buyer/apply`'s
    qualification note), each reaching a correct response and, where
    applicable, `tool_runs.status='succeeded'` with the right `entry_values`
    landing in Attio.

- Added `domain/shared/schemas.py` — Pydantic models for the shapes stored
  in `tool_runs.payload` (`BenchmarkPayload`, `ReadinessPayload`,
  `ValuationPayload`, `BuyerNetworkPayload`, one per tool, mirroring the
  corresponding `api/schemas.py` request). `pipelines.py`'s four
  per-tool payload-parsing functions used to hand-walk the stored dict with
  `payload.get(key)` plus a manual `isinstance` check per field
  (`num()`/`text()`/`count()` closures, repeated once per tool) — they now
  call `SomePayload.model_validate(payload)` and read typed attributes.
  This is a deliberate, narrow exception to the module's "no pydantic in
  `domain/`/`application/`" rule: `tests/test_architecture.py` now
  allowlists `pydantic` for exactly `domain/shared/schemas.py`'s path (a
  second `test_pydantic_allowlist_names_a_real_file` pins that the
  allowlist itself can't silently point at a deleted/renamed file). The
  models are deliberately permissive (`extra="ignore"`, no re-declared
  range/length constraints) since the data was already strictly validated
  once at the API boundary, and the stored payload also picks up the write
  contract's own bookkeeping keys later (`stage`, `ai`, `attio`,
  readiness's `score`) that these models were never meant to reject.
  `_valuation_inputs`'s discount handling keeps its `is not None` fix (an
  explicit 0% survives instead of collapsing to the 50% default) — same
  behaviour, now expressed as a typed field read instead of a raw dict
  walk. Verified with a new `tests/unit/test_schemas.py`, and live against
  the real dev Attio workspace for all three non-Bedrock tools (benchmark,
  valuation — including the 0%-discount case — and buyer network), each
  reaching `tool_runs.status='succeeded'`.

- Buyer Network's `target_geography` field changed from multi-select to
  single-select — a plain `<select>` (7 options: Bahrain, GCC-wide, KSA,
  Kuwait, Oman, Qatar, UAE) replacing the searchable click-to-toggle
  widget, since an applicant only ever targets one geography per
  application (`org_type`/`sector_focus` stay multi-select — a buyer can
  legitimately span several categories/sectors). The request/Attio field
  itself is unchanged (`target_geography: list[str]`) — Attio's own
  attribute is multiselect-typed, so the page now always sends a one-item
  list rather than the schema or domain validation changing shape.
  `test_buyers_select_options_match_the_live_validation_sets` updated with
  a plain-`<select>` option parser alongside the existing multiselect one.

## 2026-09-10

### Added

- `enrichment` module: `/enrich <name>` researches a buyer/seller's missing
  fields from public sources (Firecrawl + Bedrock), posts a diff as a Slack
  message, and writes only operator-accepted values — Attio first, then
  Postgres, via `RoleUpdaterPort` (`ddl_commands` implements the adapter).
  Also reachable from `/find-match`'s buyer-confirmation step ("enrich this
  buyer first?").
- `discovery` module: finds sellers outside the CRM (the Google-Maps lead
  search moved out of `matching_engine`), dedupes a lead against existing
  organizations, and hands a genuinely new one to a prefilled `/add-seller`
  form via `SellerDraftPort`. Reachable automatically when a `/find-match`
  run's shortlist scores below `WEB_FALLBACK_MIN_SCORE`, or on demand via a
  "Find more sellers" button on the match-result message.

### Changed

- `ddl_commands/api/slack/views/seller_add_form.py`'s add-seller form takes
  an optional `prefill` mapping, used by `discovery`'s hand-off; the
  `/add-seller` submission path itself is unchanged.
- `matching_engine` no longer owns a Firecrawl client or web-fallback view —
  both moved to `discovery`; `matching_engine` keeps only the score-based
  decision of *whether* to trigger a search.
- `server/app/modules/lead_magnets` now serves `POST /buyer/apply`, the
  sixth and last endpoint the migration spec names. Nine fields plus
  consent: `full_name`, `org_name`, `email`, `org_type`
  (`organizations.type`, 20 options pulled live from DEV Attio),
  `target_geography`/`sector_focus` (multiselect, live options),
  `check_size_min`/`check_size_max` (two USD numbers — the dropped
  `typical_check_size` bucket column and the internal `/add-buyer` Slack
  form's own fields both confirm this is the right shape, not one coarse
  range), `prior_gcc_acquisition` (free text, verified live — not
  boolean), `linkedin_url`. `org_type`/`sector_focus`/`target_geography`
  are validated against their live option sets only in the background
  Attio write, never on the request schema, so a CRM-vocabulary typo can
  never block recording the lead — the exact failure class this
  migration exists to remove.
  - Wires the previously-built but unused `LeadLLMPort.qualify_buyer`
    into a best-effort internal qualification note (same non-blocking
    pattern as readiness's advisory note), landing in
    `buyer_role.acquisition_enrichment` — the column
    `ddl_commands/api/buyers.py` already reserved for exactly this kind
    of pipeline write.
  - Two real bugs caught before either reached a submission, both pinned
    by new tests: `bootstrap.py`'s Attio writer adapter was hardcoded to
    `write_seller_role` regardless of tool despite claiming to be
    tool-agnostic — every buyer submission would have landed in the
    seller_role list. And `domain/shared/attio_values.py`'s money
    serialiser hardcoded `"seller_role"` as the currency-lookup table, so
    `check_size_min`/`check_size_max` would have raised
    `UnknownMoneyFieldError` on every submission with a check size, since
    that `(table, field)` pair only exists for `buyer_role`.
- `POST /submit-lead` — the valuation tool's own write contract, the last
  of the seven endpoints. Keeps the path the live tool already posts to
  (`dopamine-valuation.html`'s `pushLeadToAttio`). No model call: the
  blend is entirely deterministic once `/compare`'s comparables and
  `/analyze`'s discount overrides are in hand, so the result is computed
  inline rather than deferred, matching `/benchmark`. Verified live: the
  ledger's stored AI-stage output and the synchronous HTTP response for
  the same submission are bit-for-bit identical, and zero Postgres rows
  exist until the Attio write actually succeeds.
- `/analyze`'s deterministic fallback, ported from the live tool's
  `generateStrategicAnalysis`. Every regex, condition, and paragraph of
  copy was extracted programmatically from the source HTML via a Node
  harness rather than hand-typed, to eliminate transcription risk on
  ~30 paragraphs a real prospective client would read — verified by
  equivalence against the original across 113 generated cases spanning
  every regex signal and every margin/fundraise/geography boundary, 0
  mismatches. `analyze()` now falls back to it on any Bedrock failure,
  the same best-effort pattern readiness's advisory note already uses.
  Verified live: pointing `AWS_REGION` at a region with no Bedrock access
  produces the deterministic response in 1.4s, failing at the auth layer
  before any tokens are processed.
- Front end, slice 1 of 5: the GCC SME Benchmark tool now serves at
  `/benchmark/` — a verbatim copy of the live page (no script/style split
  yet), its one embedded image extracted to a content-addressed
  `static/img/<sha8>.png`, and a new `embed.js` Webflow loader with a
  `postMessage` height contract. `server/main.py` mounts `ToolStatic` at
  `/`, last, after every router. Proved two ways before merge: a local
  `uvicorn` boot exercising every route (including the bare-`/benchmark`
  307 and confirming `POST /benchmark` still reaches the API, not the
  static mount) and a real `podman build` + `podman run` image inspection
  confirming the wheel actually ships `static/`.
- Benchmark's submit call repointed from the old
  `wusool-benchmark.onrender.com/benchmark` Render relay to a relative
  `/benchmark`, rebuilding the outbound payload to the snake_case shape
  `BenchmarkRequest` requires (`extra="forbid"`) rather than just swapping
  the URL — the page's original camelCase payload would have 422'd on
  every submission. Also fixes a latent bug: the page treated any settled
  `fetch` (including a non-2xx response) as a successful submit; it now
  checks `response.ok` first.
- Front end, slice 2 of 5: benchmark's inline `<style>`/`<script>` split
  into `00-styles.css` and six numbered `.js` files, cut at the source's
  own `CONFIG`/`DATASET`/`STATE + HELPERS`/`PERCENTILE ENGINE`/`NARRATIVE`/
  `RENDER` section comments — a boundary already proven not to fall inside
  a template literal, at-rule, or load-time reader. Verified byte-exact:
  concatenating the six `.js` files in `<script src>` order reproduces the
  pre-split script body's SHA-256 exactly, and same for the CSS. Every
  `<script src>` carries `onerror="window.__lmFail=1"` and a hand-bumped
  `?v=1`, checked by one final inline sentinel script against
  `typeof render === "function"` — a failed fetch or a mid-file parse
  error now shows a fallback message instead of a silently half-working
  page. New `tests/unit/test_static_contract.py` and
  `tests/unit/test_embed_js.py` pin every `<script src>`/`<link href>`
  resolving to a real file, no committed page still carrying a base64
  image, and the outbound payload's field names matching the request
  schema — parametrized to cover each tool's `index.html` automatically as
  more of them land.
- `static/shared/height.js`: every tool page now reports its own height to
  `embed.js` via a `ResizeObserver` + `postMessage`, so an embed grows and
  shrinks with the page instead of sitting at the fixed `fallbackHeight`
  forever. Caught a real bug before any page used it: `embed.js`'s listener
  required the message to echo an `id` the parent assigned *after* creating
  the iframe, which the child document has no way to learn — every height
  update would silently have failed to match. Fixed by relying on
  `event.source === iframe.contentWindow`, which already disambiguates
  per-iframe on its own.
- Front end, slice 3 of 5: the M&A Readiness tool now serves at
  `/readiness/`, split the same way as benchmark (`00-styles.css` plus
  numbered `.js` files — one per function group here, since the source had
  no section comments to cut at) and repointed off `dopamine-relay` onto
  `POST /readiness/score`. Bigger than benchmark's repoint: the endpoint
  builds the prompt, scores it, and records the lead in one call, so
  `buildPrompt`, `callClaude`, `buildAdvisoryContent`,
  `revenueRangeToMidpointUsd`, and `pushReadinessToAttio` are deleted
  outright rather than repointed — all ported server-side already in
  `domain/readiness/readiness.py`, including a fix (`merge_advisory`) for a
  bug in the live tool where the model's advisory note silently replaced
  the deterministic one instead of adding to it. Verified the outbound
  payload matches `ReadinessRequest` field-for-field (a new
  `test_readiness_payload_field_names_match_the_request_schema` pins it)
  and that a realistic submission reaches request validation cleanly
  (fails only on the absence of a local Postgres in this environment, not
  on shape).
- Front end, slice 4 of 5: the Valuation tool now serves at `/valuation/`,
  split into `00-styles.css`, a plain (non-Babel) `10-data.js` for its
  ~180KB of pure data literals, and `20-helpers.js`/`30-components.js`/
  `40-main.js` (`type="text/babel"`, kept coarse per the migration plan —
  splitting React/JSX further buys nothing and adds silent-compile-failure
  surface). Repointed off `dopamine-relay` onto all four endpoints
  (`/enrich`, `/analyze`, `/compare`, `/submit-lead`). The live tool fired
  five independent client-composed Claude calls across its lifecycle
  (enrich, a loading-screen teaser, the full strategic read, the M&A
  readiness scorecard, and dynamic comps); `/analyze` merges four of those
  into one, so `pushLeadToAttio`, `DynamicCompsLoader`, `callClaude`,
  `RELAY_BASE`, and the teaser's own abbreviated fetch are deleted outright
  rather than repointed, and `StrategicAnalysis`/`FundraiseReadiness`
  become prop-driven off the one shared `/analyze` result instead of firing
  their own requests. `generateStrategicAnalysis` (the client's
  deterministic port) survives only as `LockedPreview`'s fallback while
  `/analyze` is in flight — everywhere else `/analyze`'s own server-side
  fallback already covers the failure case.
  - Two dead-code findings bigger than already documented: the *entire*
    Webflow-exported nav/footer CSS block (59 lines, not just the two
    selectors previously named) had zero JSX usages of any class in it,
    and its one inline image was a 122.5KB JPEG mislabeled `image/png` on
    a class also never referenced — both verified by grep before deleting,
    both gone. Valuation's logo turned out byte-identical to readiness's,
    deduped for free. Total served weight (`index.html` + 5 files): 327KB,
    down from the original single file's 564KB.
  - One simplification, noted rather than hidden: `/analyze`'s response
    shape cannot distinguish a Bedrock success from its own deterministic
    fallback, so `StrategicAnalysis`'s "AI-powered"/"Based on X's profile"
    copy — previously conditional on which one happened — now always
    shows. Cosmetic only; the fallback content is a verified exact port of
    the live tool's own local-fallback text either way.
  - Two request fields the schemas accept but the page deliberately never
    sends, both pinned explicitly by
    `test_valuation_payload_field_names_match_their_request_schemas` (so a
    third field going missing still fails it): `AnalyzeRequest.website_text`
    (the client-side scraping that ever populated it was already dead
    before this migration) and `ValuationRequest.discounts` (`TradingComps`
    and `TransactionComps` keep independent discount sliders, so there is
    no single value to forward — the server already defaults to 50%/50%).
  - Verified past the usual byte-exact-concat and per-file-Babel-transpile
    checks: a full headless run using the real `@babel/standalone@7.25.6`
    and React/ReactDOM 18.3.1 UMD builds against jsdom, served live over
    HTTP from a local `uvicorn`, driving the actual Gate form through
    submission and confirming `/enrich`, `/analyze`, `/compare` and
    `/submit-lead` each fire with exactly the request body their schema
    expects, and that the unlocked report (Strategic Analysis, the
    readiness scorecard, Trading Comparables) renders the fetched data
    correctly end to end.
- Front end, slice 5 of 5 (last one): the Buyer Network tool now serves at
  `/buyers/`, posting to `POST /buyer/apply`. Unlike the other three, there
  was no live tool to port — the Buyer Network only ever ran on a Tally
  form — so this is a new page: `index.html` + `00-styles.css` +
  `10-main.js`, built to the same visual language as the ported tools
  (shares the logo image, same navy/sky palette) but with no prior
  monolith to slice, so no concat-byte-exactness invariant applies here.
  Its 9 fields plus consent match `BuyerApplyRequest` exactly
  (`test_buyers_payload_field_names_match_the_request_schema`), and its
  three multiselects (`org_type` 20 options, `target_geography` 7,
  `sector_focus` 85) use plain `<select multiple>` with every `<option>`
  generated straight from `domain/buyer_network/buyer_network.py` and
  `domain/shared/sector_options.py` — the same live Python option sets the
  background Attio write validates against — rather than hand-typed, and
  pinned in sync by a new
  `test_buyers_select_options_match_the_live_validation_sets`: these
  fields aren't checked by the request schema itself (only the background
  write is), so a typo'd option would otherwise record the lead and then
  silently fail to land in the CRM. Verified with the same jsdom-over-HTTP
  method as the other three: filled every field including both
  multiselects, submitted, and confirmed the POST body matches
  `BuyerApplyRequest` field-for-field and the success view replaces the
  form. Also confirmed live that `/buyers/` (the static page, plural) and
  `/buyer/apply` (the API, singular) were never even a near-collision, the
  way `/benchmark`, `/readiness/score` and the others required checking.
  This is the last of the four tools — the migration's front-end work is
  complete pending the cutover steps in the migration plan (Firecrawl
  verification, Cloudflare DNS, Webflow paste-in, one-line `embed.js`
  switch per tool).
- `server/app/modules/lead_magnets/DEPLOYMENT.md` — the deploy runbook for
  this module: what `_deploy.yml` already does automatically vs. the
  one-time human steps (Secrets Manager keys, `LEAD_MAGNET_ALLOWED_ORIGINS`,
  Cloudflare DNS before the `toolkit_extra_hostnames` apply, the SSM
  bootstrap re-run, and the Webflow paste-in order — benchmark first,
  Buyer Network last since its rollback also means re-enabling Tally).

### Changed

- `lead_magnets`' `domain/`, `application/`, and `api/` regrouped by tool
  (`valuation/`, `benchmark/`, `readiness/`, `buyer_network/`) with a
  `shared/` subpackage for what two or more tools genuinely depend on —
  the ledger vocabulary, the write contract, the sweeper, the Bedrock/
  Attio clients. `persistence/` and `providers/` stay flat: one ledger
  and one set of clients for every tool, not four duplicated copies.
  File structure only, no behavioural change — all tests passed
  unmodified in substance (import paths only) before and after.
- `application/shared/base.py` + `service.py`: `bootstrap.build_submission_service`
  now returns one composed `LeadMagnetService` instead of wiring
  `Pipelines` and `SubmissionService` together by hand. Composition, not
  the multiple-inheritance mixin split the modular-monolith guide
  generally prescribes — the two take genuinely different Ports and are
  deliberately tested standalone, so forcing them into shared-state
  sibling mixins would make every pipeline-only or submission-only test
  fake Ports it has no use for. Purely additive: `Pipelines` and
  `SubmissionService` are unchanged, every existing test against them
  passes unmodified.
- Buyer Network's three multiselects (`org_type`, `target_geography`,
  `sector_focus`) replaced the native `<select multiple>` with a plain,
  searchable, click-to-toggle widget — no library, matching this page's
  existing vanilla-JS style. The native control needed ctrl/cmd+click to
  pick more than one option, which is not discoverable in a public lead
  form; a plain click now toggles a row independently of any other
  selection, and typing filters the list (useful on `sector_focus`'s 85
  options). Every `<option>` was regenerated from the same live Python
  option sets as before (`domain/buyer_network/buyer_network.py`,
  `domain/shared/sector_options.py`), not hand-edited, and
  `test_buyers_select_options_match_the_live_validation_sets` was updated
  to parse the new markup rather than the old `<select>`. Verified with a
  full headless run: typed "fintech" into the 85-option sector list and
  confirmed it narrowed to one match, clicked two unrelated options with
  plain clicks and confirmed both stayed selected, clicked one again and
  confirmed it toggled off, then submitted and confirmed the POST body
  carried every selection correctly.

### Fixed

- Six findings from a full code review ahead of deploying the lead-magnet
  migration, all confirmed by direct code reading before being fixed and
  re-verified live against the real dev Attio workspace where applicable:
  - **Every submission created a duplicate Attio organization.**
    `bootstrap.py`'s `_RoleAttioWriter.write()` never passed an existing org
    id through to `role_writer.py`, so it always took the `create_organization`
    branch — never `patch_organization`. `domain/shared/dedup.py`'s
    `org_key`/`person_key` (whose own docstring says this is "what stops the
    second one creating a second Attio organisation") were grepped and
    confirmed unused anywhere outside their own tests. Added a new pure
    `domain_matches()` helper (name-similarity search via the existing
    `OrganizationRepository.search_by_name`, then a domain-match filter — an
    empty domain never matches, so name alone can't accidentally merge two
    distinct companies) and wired it into `_RoleAttioWriter`. Verified live:
    seeded Postgres with what the Attio webhook mirror would normally write
    (disabled locally under `ATTIO_IS_TEST=true`), then confirmed a second
    tool submission for the same company+domain reused the existing
    `organization_attio_id` instead of creating a new one, even with a
    different URL form of the same domain.
  - **An explicit 0% valuation discount silently became the 50% default.**
    `pipelines.py`'s `_valuation_inputs` used `discounts.get(...) or default`
    — `0 or 50.0` is `50.0` in Python — while `api/valuation/endpoints.py`'s
    synchronous response correctly used `is not None`. The figure permanently
    recorded in Attio diverged from what the visitor actually saw and chose.
    Fixed to the same `is not None` shape.
  - **A real XSS gap** in `static/readiness/40-results.js`: model-generated
    dimension/recommendation text was spliced into `innerHTML` unescaped in
    four places, while the line above already correctly used `.textContent`
    for the same kind of data. The prompt embeds the visitor's own free-text
    answers, so an echoed injection would execute live on the results page.
    Added a small `esc()` helper and applied it to all four fields.
  - **The interactive valuation report's client-side DCF calc omitted the
    30% DLOM** (`domain/valuation/valuation_methods.py`'s `_DEFAULT_DLOM_PCT`)
    both places it's computed client-side (`30-components.js`'s `DCFModule`
    and `40-main.js`'s pre-calc that seeds it) — showing the visitor an
    equity value ~1.43x higher than what the server actually blends and
    writes to Attio for the same submission. Added a matching `DLOM_PCT`
    constant and applied it in both places.
  - **A genuine $0 valuation was silently dropped from the Attio write.**
    `valuation_values()` used `result.low or None`, and `value_company()` can
    legitimately return 0 for every figure when no method produces a usable
    row — making a submission whose valuation genuinely computed to zero
    indistinguishable in Attio from one where valuation was never attempted.
    Fixed by passing the values through directly. This surfaced a **second,
    more severe pre-existing bug** while writing the test for it:
    `valuation_low`/`mid`/`high` were never in `_SELLER_MONEY`, so they were
    never routed through `serialize_money()` at all — every valuation write,
    zero or not, sent a bare float instead of the `{"currency_value": ...}`
    shape Attio's `currency`-type attribute requires (`money.py`'s own
    `_CURRENCY_CODE_BY_FIELD` already configures all three, just never
    consumed for this path). Added them to `_SELLER_MONEY`. Live-testing the
    fix surfaced a **third** bug in the same path: `serialize_money()` never
    rounded, and a blended valuation (several ratios multiplied together)
    routinely produces more than Attio's 4-decimal-place limit on
    `currency_value`, confirmed live (`Must have no more than 4 decimal
    places`). Fixed by rounding to 2 decimal places in `serialize_money()`
    itself, benefiting every caller of the shared `attio/providers/attio/
    money.py`, not just valuation. Verified live end-to-end after both
    fixes: a real `/submit-lead` valuation now reaches `status='succeeded'`
    with a real Attio organization and seller_role entry.
  - Benchmark's percent-field validation silently accepted non-numeric input:
    `static/benchmark/30-helpers.js`'s `num(v)` returns `null` for garbage
    text, and JS coerces `null<0`/`null>100` to `false`, so the range check
    let it through with no inline error. Fixed with an explicit
    `n===null` check alongside the range check. UX-only — backend Pydantic
    bounds checks already protect the actual data — but fixed for
    consistency with the rest of this review.
- `domain/shared/attio_values.py::benchmark_values` sent `benchmark_quartile`
  as a bare digit (`str(result.quartile)`, e.g. `"2"`) — the real Attio
  attribute is a select with option titles `Bottom 25%`/`Below Average`/
  `Above Average`/`Top 25%`, not free text (`SCHEMA.md`'s "text" is wrong for
  this one field). Caught live: pointed the local stack at the real dev
  Attio key and a real `/benchmark` submission's background Attio write
  failed with `Cannot find select option with title "2"`, while the
  write-ahead ledger correctly kept the lead (`tool_runs.status='failed'`
  with the error captured, nothing lost). A first MCP-tool-based audit of
  the workspace wrongly concluded ~20 other attributes and `is_test` were
  also missing everywhere — the Attio MCP server's attribute-listing tools
  were silently under-reporting (33 of the real 59 attributes on the
  `seller_role` list, and fabricated `readiness_band`'s options as `Yes`/
  `No` when the real options are the 4 bands the code already sends).
  Re-verified every field against Attio's raw v2 REST API directly instead
  of the MCP abstraction: everything else in the whole module — `is_test`,
  `readiness_band`, `recommended_referral`, benchmark's other 20 fields,
  `lead_priority`, `quality_check`, `benchmark_band`, buyer's org_type/
  target_geography/sector_focus, valuation's 3 fields — was already
  correctly wired to a real, matching attribute. Fixed with a
  `_QUARTILE_TITLES` lookup, same fallback-to-raw-value shape as the
  existing `readiness.py::attio_band()`. Re-verified against the real
  workspace after the fix: the same failing case (score 48, quartile 2) now
  lands in Attio as `benchmark_quartile: "Below Average"`, confirmed
  straight from the v2 API, not just Postgres.
- `application/shared/sweeper.py`'s `sweep_once` was fully built and unit
  tested but never actually invoked — no `run_sweeper_forever` existed and
  `main.py`'s `_lifespan` started no background loop for it, so a
  submission whose AI/Attio completion step failed would sit
  `status='failed'` in `tool_runs` forever with nothing to retry it (the
  lead itself was never lost — the write-ahead ledger already guarantees
  that — but it wouldn't self-heal either). Caught writing the deploy
  runbook (`DEPLOYMENT.md`), not by a test, since nothing exercised the
  gap directly. Added `bootstrap.run_sweeper_forever()` (one pass
  immediately at boot, then every `LEAD_MAGNET_SWEEPER_INTERVAL_S`; a
  failed pass is logged and never stops the loop) and started it as a
  cancelled-on-shutdown `asyncio.Task` in `main.py`'s `_lifespan`.
  `sweeper.py`'s `submissions` parameter now types against the composed
  `LeadMagnetService` (`bootstrap.build_submission_service`'s own return
  type) instead of the bare `SubmissionService`, so the loop can reuse the
  same factory `run_completion` already does rather than re-wiring
  `Pipelines`/`SubmissionService` by hand. New `test_bootstrap.py` pins
  that a raised exception on one pass doesn't stop later passes and that
  cancellation actually propagates rather than hanging.
- `embed.js`: `iframe.src = config.src` assigned a root-relative path
  (e.g. `"/benchmark/"`) directly, which the browser resolves against the
  *parent* page's own origin, not the tools host — `toolsOrigin` was
  already computed correctly (used for the `postMessage` origin check)
  but never applied to the iframe's own `src`. On the real Webflow
  deployment this would have sent every embed to
  `wusoolcapital.com/benchmark/` instead of the tools server, 404ing
  there rather than loading the tool. Caught testing locally: a plain
  `file://` page with the embed script produced an iframe pointed at
  `file:///benchmark/`, nothing rendered. Fixed to
  `iframe.src = toolsOrigin + config.src`; pinned by a new
  `test_iframe_src_is_built_absolute_from_tools_origin`.
- Readiness's own sector dropdown (`dopamine-readiness-score.html`'s
  `#cSector`, 11 real options) had no entry in `sector_mapping.py` — a
  curl test against a throwaway DB raised `UnmappedSectorError` on 10 of
  the 11, e.g. `"F&B & Hospitality"`. Only `"Other"` happened to collide
  with benchmark's own vocabulary and work by coincidence. The lead was
  never lost (the write-ahead ledger already guarantees that), but the
  CRM entry would never have gotten a `sector_focus` classification.
  Added `READINESS_SECTORS`, merged into the existing lookup. One
  compound, `"F&B & Hospitality"`, gets the same flagged-default
  treatment as the pre-existing `"DeepTech or hardware"` case — mapped
  to `Food & Beverage / QSR` as the more common case for a generalist
  SME tool, not a settled decision.
- The valuation tool's own 225-label vocabulary (`ALL_SECTORS`) had the
  same gap, at far larger scale: 204 labels with no `sector_focus`
  target, confirmed by actually running `to_sector_focus()` against the
  real list rather than trusting this file's own stale docstring, which
  had said 214 — itself wrong, corrected in the same commit. Added
  `VALUATION_SECTORS` covering all 204; 0 of the tool's 225 labels now
  raise `UnmappedSectorError`. 204 fine-grained VC/startup labels against
  an 85-option CRM taxonomy means several targets are real judgment
  calls — 15 flagged in `_VALUATION_SECTORS_FOR_REVIEW`, each with its
  reasoning and the plausible alternative, worth a second look from
  someone with sector-taxonomy context.

## 2026-09-09

### Added

- `server/app/modules/lead_magnets/` — the first slice of moving the four
  lead-magnet tools (Valuation, M&A Readiness, GCC SME Benchmark, Buyer
  Network) off Vercel + Render + Tally and onto the toolkit instance, with
  the AI on Bedrock through the instance role so no API key exists. Landed
  in this slice: `Settings`, `domain/dedup.py`, the `tool_runs` write-ahead
  ledger, the write contract and its sweeper, the Bedrock and Firecrawl
  providers, and the API guards + static handler. 85 tests.
  - The write contract records every submission **before** any AI or Attio
    call, which is what makes a lost lead impossible. `complete()` takes a
    ledger row rather than a fresh payload, so a first attempt and a sweeper
    resume are one code path: a run never re-earns AI output it already paid
    for, and never writes Attio twice.
  - Retry ceilings are per failure class, as one SQL `CASE`: a failed Attio
    write retries (the AI output is stored), a valuation/benchmark AI failure
    resumes once from the deterministic fallback, and readiness — which has
    no fallback by decision — never retries.
  - No new Attio→Postgres sync code. `ddl_commands`' existing webhook mirror
    already maps every lead-magnet and benchmark column, so this module
    writes Attio and lets the mirror follow.
- `apps[*].extra_hostnames` on `modules/toolkit-ec2`, joined into Caddy's
  site addresses so one container serves several hostnames.
  `toolkit_extra_hostnames = ["tools.wusoolcapital.com"]` and
  `toolkit_instance_type = "t3.small"` in `envs/prod.tfvars` (prod was on the
  `t2.micro` default, 1GB, already running the Slack bot). Also adds `encode
  zstd gzip` to the Caddy site block. Chosen over a second `apps` entry,
  which would need its own secret, ECR repo and image build while
  `_deploy.yml` names `toolkit` literally in three steps — and would not
  isolate failure, since `apps` renders one compose file and one bootstrap.
- `utilities/domain/bedrock.py` — `extract_json`, `TRANSIENT_ERROR_CODES` and
  `converse_kwargs`, shared by every Bedrock caller. `meetings` and
  `matching_engine` each carried a byte-identical `_extract_json`, and
  meetings' own docstring warned to check the other copy when fixing either;
  a third caller would have made that unfollowable.

### Changed

- `AttioNoteWriter` moved from `meetings/providers/attio/note_writer.py` to
  `attio/providers/attio/notes.py`. The `note` object slug and attribute
  shape are workspace-level facts, and `server/tests/test_architecture.py`
  allows deep cross-module imports only into the full-access modules, so
  `lead_magnets` could not have reused it in place. `note_type` is now a
  required constructor argument — no default, since `notes.note_type`'s CHECK
  allows exactly `Meeting` or `Manual`.

### Fixed

- `implied_ev_low`, `implied_ev_high` and `ebitda_adjusted` were missing from
  `attio.providers.attio.money._CURRENCY_CODE_BY_FIELD`. The columns landed
  with `f7a2c9e14b83` but had no writer, so the first benchmark submission
  would have raised `UnknownMoneyFieldError`. All three are USD, as
  `SCHEMA.md` already declared.
- A latent bug in the planned write contract, caught before it shipped:
  `tool_runs`' subject columns are foreign keys into the Postgres mirror, but
  at the moment an Attio write returns those rows exist only in Attio, so
  setting them FK-violated on every genuinely new lead. `finish()` seeds both
  parent rows `ON CONFLICT DO NOTHING` and resolves role FKs by a
  `legacy_entry_id` subquery that is NULL until the mirror lands;
  `promote_role_fks()` back-fills them.
- `infrastructure/terraform/README.md` said prod `create_instance` defaults
  to `false`; `envs/prod.tfvars` has set it `true` since 2026-08-17.

### Notes

- The module does **not** serve yet and is not registered in
  `server/main.py`. The endpoints, the prompts, the deterministic fallbacks
  and the tool pages need the four HTML files and `index.js` from
  `dopamine-relay`/`wusool-benchmark` (private, personal account) and
  `sector_mapping.py`; Firecrawl's half of the comparables pipeline is still
  unverified end to end. Recorded in the module README's "Blocked on".
- Resolves a contradiction across the three handover documents: money is
  **USD everywhere**, per docs 1-2 and the code (`utilities.domain.Money`
  types `currency` as `Literal["USD"]` and raises otherwise). Doc 3's
  "valuation and readiness are AED" is stale, and deleting the tools'
  `toAed()` belongs with the repointing work, as this file's 2026-09-07 entry
  already said.
- Two handover items were already done and needed no work: prod Bedrock
  access (`envs/prod.tfvars` has had `enable_bedrock = true` with both
  granted models since before this branch), and the Attio→Postgres receiver
  for lead-magnet fields.

## 2026-09-08

### Changed

- `docs/handover/`, `docs/technical/`, and `docs/user-guide/` are each split
  from one long `README.md` into a per-feature GitBook page tree
  (`docs/SUMMARY.md`, `docs/.gitbook.yaml`), so the docs can be imported into
  GitBook and delivered to the client with a screenshot slot per feature.
  Dev-only content (raw dev URLs, dev/prod comparison tables, the `is_test`
  cutover mechanics, and internal-only outstanding items) moved to
  `docs/dev/ATTIO_SOURCE_CUTOVER.md` and `docs/dev/INTERNAL_OUTSTANDING.md`;
  the client-facing pages are prod-only. Added a WusoolScribe half to the
  user guide and a `technical/scribe-desktop.md` page — the desktop app and
  the `meetings` server module previously had no client-facing
  documentation at all.

### Fixed

- `/edit-seller`/`/edit-buyer` failed on `organizations.client_type` with an
  "objects attribute" option error and saved nothing. The field is declared a
  `select` with nine options, but it is plain `text` in the SOURCE Attio
  workspace (options list empty) — the option lookup matched nothing and
  raised before any write. It is now a `multi_select_as_text` field: operators
  still pick from the nine titles, and the picked ones are written comma-joined
  as a bare string, the shape #123 documented for both sides and the shape
  `attio_sync.py` already reads back.

### Added

- `multi_select_as_text` `FieldKind`, for an attribute that is plain `text` in
  Attio but has a fixed vocabulary operators shouldn't have to retype. Renders
  Slack's multi-select, stores `", "`-joined titles. Distinct from
  `multi_select_text`, which is a real Attio multi-select writing option IDs
  into a `text[]` column.

## 2026-09-07 (yet again)

### Fixed

- WusoolScribe 0.4.8: every `ScrollArea` surface (sidebar meeting list,
  settings, folder view, transcript panel, model manager, dialogs) showed a
  duplicate native scrollbar alongside the shadcn/Radix one. Radix hides the
  native bar via a runtime-injected `<style>` tag, which Tauri's nonce'd
  `style-src` CSP silently drops — the same class of issue #117 hit with
  Sonner's stylesheet. The hiding rule is now shipped in `globals.css`
  instead, scoped to `[data-radix-scroll-area-viewport]`.

## 2026-09-07 (even later)

### Changed

- **`meetings` now files a note for every meeting, not just the ones with
  a resolved organization.** The early return that skipped org-less
  meetings entirely (internal/general/investor, or a company that never
  resolved to an Attio org) is removed — `notes.organization_id` was made
  nullable specifically for this case back on 2026-08-29, but the
  meeting-summary pipeline never started using it. Both Postgres and Attio
  now get the note; an org-less Attio note omits the `organization_id`
  key rather than sending an empty reference.
- **Meeting notes now link to the org's active buyer/seller-role row.**
  When a note's meeting is buyer-primary or seller-primary,
  `notes.buyer_role_id`/`seller_role_id` are set to that org's
  most-recently-created *active* `buyer_roles`/`seller_roles` row (never
  both) — new `RoleLookupPort`/`RoleLookup` in `meetings/persistence/`,
  since `buyer_roles`/`seller_roles` have no owning module to wrap. The
  same row's `legacy_entry_id` is sent to Attio's `buyer_role_id`/
  `seller_role_id` text attributes. The link is skipped on both sides
  when the row has no `legacy_entry_id` — `ddl_commands`' inbound note
  sync (`_NOTE_UPSERT`) re-resolves those columns from whatever Attio
  holds on every `note.created`/`note.updated` webhook, so sending a
  Postgres id with nothing on the Attio side would let the next webhook
  silently overwrite it back to NULL.
- **`AttioNoteWriter.push_note` now actually writes `notes.primary_role`**
  (schema added the same day by `b4e1d7c0f3a2`, but nothing wrote it yet)
  — the meeting's seller/buyer/investor/internal/general tag, sent to
  Attio's existing `note.primary_role` select and to the Postgres column,
  both via the shared native `meeting_role` enum.
- **New `meetings.primary_role`**, reusing the same `meeting_role` enum —
  promotes the role tag out of `meetings.metadata` jsonb (where
  `encode_role_metadata` already stashed it) into a queryable column, so
  internal/general meetings can be filtered out of a notes listing without
  needing an org to anchor them. `notes.primary_role` is set from this
  column at publish time.
- **New `meetings.note_id`**, written back once a meeting's note exists,
  so a meeting can be traced to the CRM note it produced. Postgres-only —
  Attio has no meeting object.
- `NotesRepository.create` now runs inside its own savepoint
  (`begin_nested()`). Every meeting reaching the notes insert (not just
  org-having ones, as before) meant a failed insert could otherwise poison
  the whole session and silently roll back the `mark_completed` a few
  statements earlier, stranding the meeting in `summarizing` forever.
- Migration `f5cd5212e82e` (on top of `b4e1d7c0f3a2`): `meetings.primary_role`
  (reusing the `meeting_role` type), `meetings.note_id` + `fk_meetings_note_id`.
  No backfill — both databases were cleared before this change.

## 2026-09-07 (later still)

### Added

- **`notes.primary_role`** — which side the meeting a note came from was
  about, so internal meetings can be filtered out of the Attio UI. A Select
  on Attio's `note` object and the native Postgres enum `meeting_role`
  (migration `b4e1d7c0f3a2`), so both sides can filter rather than only
  string-match.
  - The five option titles are **lowercase** (`seller`, `buyer`, `investor`,
    `internal`, `general`): they are the `MeetingRole` `StrEnum` values
    (`meetings/domain/roles.py`) and the server sends the enum's string
    straight through. Attio select values are case-sensitive, so title-casing
    them there would fail the write or silently create a second set of
    options. Deliberately *not* patterned on the neighbouring `note_type`,
    whose `Manual`/`Meeting` are capitalised.
  - Nullable, with no backfill: a manual note has no role, and neither does
    anything written before today.
  - Wired through both read paths — the webhook upsert
    (`persistence/attio_sync.py`) and the nightly
    `sync-notes-from-source.ps1` — plus the attribute declaration in
    `backfill-notes.ps1`, which owns the `note` object's schema.
  - Nothing writes it yet. `AttioNoteWriter.push_note` would have to take the
    role, which means widening `NoteWriterPort`, and choosing *which* of a
    meeting's reconstructed roles is the primary one — a product decision,
    not a schema one.

## 2026-09-07 (later)

### Changed

- **One SOURCE Attio workspace now serves both environments.** The separate
  DEV workspace is retired; `ATTIO_IS_TEST` says which half a process owns.
  Every server-side Attio create stamps `is_test`, and every ingest path
  skips the other half.
  - `ATTIO_IS_TEST` is a new setting on the `attio` module, deliberately
    independent of `APP_ENV` — Terraform says `dev`/`prod` while
    `.env.example` said `development`, and binding CRM-data correctness to
    environment-name spelling across two vocabularies is the ambiguity to
    avoid. It defaults to `true`, because the two failure directions are not
    symmetric: a prod deploy that forgets it hides new records (loud,
    bounded, reversible), whereas a dev deploy that forgets it writes test
    data into production (silent, unbounded). The deployed environments get
    it from `var.environment` in `modules/toolkit-ec2`, so it cannot be
    forgotten.
  - **Patches never re-assert `is_test`.** It describes where a record came
    from, not who is editing it. A read-before-write guard refuses a
    cross-scope edit instead, and `resolve_role_entry_id` filters by scope
    inside its existing page-through, so the role side costs no extra calls.
  - Role syncs filter the trigger *before* `_fetch_siblings` and filter the
    siblings too. `_reconcile_active_entry` writes back to Attio, so an
    unfiltered reconciliation would let a newer test entry demote a real
    production entry to `is_active=false` — corrupting the flag
    `resolve_role_entry_id` and the matching engine both read.
  - The webhook route ignores deliveries entirely in test scope, and now
    validates `workspace_id`, which was already parsed and thrown away.
  - The nightly full resync refuses to start in test scope rather than
    overwriting the dev sandbox, and moved from the dev environment to prod.
  - `/find-match` needed no change: `matching_engine` never calls Attio.

### Removed

- `infrastructure/crm-sync/scripts/dev-attio/` (~6.5k lines) and
  `server/scripts/postgres-sync/dev/`. The dev database is no longer synced
  from Attio at all — it is a sandbox that developers fill with `/add-*`.
  A fresh dev database is therefore empty, and `/find-match` has nothing to
  match against until someone creates buyer roles by hand; that is by
  design. `rds-tunnel-runbook.md` moved up out of `dev/` (prod's README
  links to it) and now covers both environments.
- The legacy standard `deals` object is out of the webhook's scope. It has
  **no `is_test` attribute**, so its records could never be assigned to an
  environment — a hole straight through the new filter. The nightly prod
  sync already deleted any row it produced, since that only fetches `deal`.
  The `deals` *PostgreSQL table* is unrelated and unchanged.
- `ATTIO_DEAL_OBJECT_SLUG`, and the per-workspace attribute-slug fallbacks
  in every params-mapper. Each first branch was verified absent from
  SOURCE's live attribute lists before deletion, enumerating each object in
  full rather than keyword-searching — a fuzzy query for "role title"
  returned only `job_title` and would have led to deleting `person.role`,
  which is live and stayed.
- `build_note_writer()`'s availability gate, which made note pushes silently
  optional. `ATTIO_NOTE_OBJECT_SLUG` is a constant now, so
  **`ATTIO_API_KEY` is effectively required for the `meetings` module** —
  safe today because the toolkit deploys one app in one container whose
  `ddl_commands` settings already require it.

### Fixed

- `source-attio/config/target-schema.json` said `person.postgres_table` was
  `"people"`; the model is `"person"`. The retired `dev-attio` copy had it
  right, so it was corrected before that directory was deleted.

## 2026-09-07

### Added

- Lead-magnet schema across SOURCE Attio and PostgreSQL, so the four tools
  (Valuation, M&A Readiness, GCC SME Benchmark, Buyer Network) have a real
  destination for what they compute. Until now those fields were written
  only to the legacy `lead_magnet_inbound*` Attio lists, which the Postgres
  mirror does not read — none of it reached the database.
  - 26 attributes on the `seller_role` list and matching `seller_roles`
    columns: benchmark score/band/quartile, nine `pct_*` percentile
    rankings, `implied_ev_low`/`_high`, `ebitda_adjusted`, `headcount`,
    `days_to_get_paid`, `data_consent`, the routing and dataset-governance
    fields, and `recommended_referral`.
  - The nine percentiles are discrete columns, not one JSONB blob, so each
    stays filterable — the reason they are real columns rather than
    `raw_attio`, which the nightly resync overwrites wholesale.
- `is_test` (checkbox) on all six Attio entities — `organizations`,
  `person`, `deal`, `note`, `seller_role`, `buyer_role`. One SOURCE
  workspace now serves both environments: `true` is dev/test, `false` is
  production. **Attio-only, with no PostgreSQL column** — the split is a
  read-side filter at sync time. Every write path sets it explicitly.
  (Corrected 2026-09-07: this entry originally said an unset record "matches
  neither filter and disappears from both environments". That is true of
  Attio's UI filter chips but **not** of the REST API, where `is_test eq
  false` does match records with no value — verified against a real record.
  It is why the sync can skip only an explicit `true` and does not depend on
  a stamping run having happened.)
- `tool_runs` table (`tool_run.py`, Postgres-only) and
  `activities.tool_run_id`. Complements `activities` rather than replacing
  it. Every subject reference is nullable with no CHECK requiring one —
  `activities_subject_present` makes it impossible to record a submission
  that failed before its Attio write, which is the lead-loss case the
  ledger exists to catch.
- Missing picklist options: `seller_role.readiness_band` (Early,
  Developing, Sale Ready, Market Ready), `buyer_role.target_geography`
  (Egypt, Global), `organizations.type` (Search Fund, HNWI).

### Fixed

- `seller_role.readiness_band` shipped as a select with **zero options**, so
  every write to it failed outright. Any readiness band written before now
  was silently lost.
- `server/scripts/postgres-sync/dev/sync-postgres.ps1` declared 31
  `seller_roles` columns against 30 `%s` placeholders — that insert could
  never have executed. Pre-existing and unrelated to the work above, but it
  sat in the block being edited.

### Notes

- Schema only: the tools are **not** repointed. `dopamine-relay` and
  `wusool-benchmark` are untouched, so Valuation and Readiness still run
  `toAed()` and write AED into USD-declared attributes. Deleting that
  conversion belongs with the repointing work.
- Alembic `f7a2c9e14b83`, revises `2565f7950641`.

## 2026-09-06

### Added

- `GET /desktop/verify` on the `meetings` module's desktop API surface, so
  the WusoolScribe desktop app's Scribe Push settings tab can check a
  server URL + API key against the backend before saving them, instead of
  only surfacing a bad config the next time the user pushes a meeting.
  Reuses the existing `require_desktop_api_key` dependency — the route
  body just confirms the Bearer token was accepted. New
  `verify_push_config` Tauri command in the desktop app calls it and
  blocks `set_push_config` from persisting on a rejected key or
  unreachable server.
- WusoolScribe desktop app: the "Summarize meeting" dialog now auto-polls
  `GET /desktop/meetings/{id}` every second after a push instead of
  requiring a manual "Check" click, stopping once the summary arrives. An
  in-flight guard keeps a slow response from ever piling up overlapping
  requests, and background-poll failures are silenced (a manual click
  still surfaces one) so a transient error doesn't spam a toast every
  second.

### Fixed

- WusoolScribe desktop app: Scribe Push save failures now show a short,
  non-technical toast ("Could not reach the server. Check the URL and your
  connection.") with no endpoint hostname or raw reqwest/DNS chain; the full
  error goes to the log instead of the UI.
- WusoolScribe 0.4.7: bundle Sonner's base stylesheet explicitly so Settings
  feedback remains visible in packaged builds. Successful Scribe Push saves
  now show one "Push destination saved" toast after verification and persistence.
- WusoolScribe desktop app: `ScrollArea` viewports now inherit the Root's
  max-height, so scroll surfaces bounded only by `max-h-*` (language picker,
  company autocomplete, release notes, pushed summary, chunk progress, and the
  Ollama model lists) scroll instead of silently clipping their overflow.
  Sticky transcript headers keep Radix's content wrapper as `display: block`.
- WusoolScribe desktop app: standardized application scroll surfaces on the
  shared shadcn/Radix `ScrollArea`, including the transcript viewport, dialogs,
  settings, onboarding, and pickers, so the scrollbar thumb follows light and
  dark themes consistently.
- WusoolScribe desktop app: removed redundant in-page Back buttons from the
  Settings and folder pages; navigation remains available through the sidebar.
- `meetings` module: the pushed meeting's `occurred_at` was computed
  server-side as `now() - duration_seconds`, which is wrong whenever a
  push happens well after the meeting itself (e.g. the next day) — the
  desktop app now computes and sends the actual `occurred_at` itself
  (derived from the local recording's saved timestamp minus its
  duration), and the server uses that value verbatim instead of guessing
  from its own clock.
- WusoolScribe desktop app: a meeting folder's list (and the main
  sidebar) relied implicitly on the SQLite query's `ORDER BY created_at
  DESC` surviving unchanged through every consumer with no sort of its
  own; now explicitly sorted latest-first once, at the single shared
  source (`SidebarProvider.fetchMeetings`), so it can't silently break if
  that array is ever touched elsewhere.
- WusoolScribe desktop app: the native macOS title bar and the sidebar's
  scrollbar both stayed in light mode regardless of the app's own
  dark-mode toggle. `tauri.conf.json`'s window `theme` only set the
  chrome once at launch, so it never followed later toggles — now synced
  via the Tauri window API on every theme change. The scrollbar's
  `::-webkit-scrollbar` CSS was silently ignored (WKWebView/Safari
  doesn't reliably support it) — switched to the shadcn `ScrollArea`
  (Radix, DOM-drawn), which isn't subject to that WebKit limitation.
- WusoolScribe desktop app: the tray/menu-bar icon reused the app's
  window icon instead of the dedicated `tray-icon.png`; the About
  dialog's logo now has rounded corners.

## 2026-09-05

### Added

- New `meetings` module: ingests transcripts pushed by the WusoolScribe
  desktop app, summarizes them via AWS Bedrock (forced-tool-call Converse,
  its own 300s-timeout client — a system-prompt capability
  `matching_engine`'s shared Bedrock client doesn't have), and writes the
  existing `meetings`/`notes` tables, optionally pushing the note to Attio
  when `ATTIO_NOTE_OBJECT_SLUG` is set. Async POST-then-poll contract
  preserved so the desktop app's Rust client is unchanged; runs as a
  `BackgroundTask` in the existing toolkit process — no SQS, no worker
  containers. This replaces Scribe's entire server-side summarization
  pipeline; the desktop app's own recording/local transcription is
  unaffected and out of scope, as is Slack delivery. `meetings` gains 5
  additive columns (`status`, `install_id`, `local_recording_id`,
  `summary_json`, `summary_started_at`) via one migration; this repo is now
  the writer of that table (previously Scribe, via the `scribe_pub` role —
  see `docs/dev/SCRIBE_INFRA_CONTRACT.md`, decommissioning that role and
  Scribe's EC2/SQS infrastructure is a separate follow-up). Prod's toolkit
  Terraform now enables Bedrock access (`enable_bedrock = true` +
  `bedrock_models`), previously dev-only.
- WusoolScribe desktop app: enabled the in-app auto-updater end to end. New
  `stacks/scribe-updates` Terraform stack (S3 + CloudFront, no custom domain
  yet) hosts a per-channel `latest.json` manifest and signed macOS
  `.app.tar.gz` payloads, published by a new manual-dispatch-only
  `scribe-release.yml` workflow restricted to a `scribe-release` GitHub
  Environment (**create it by hand, no protection rules needed, before the
  first run — the release role is unassumable without it**; the environment
  is purely an OIDC-trust label, `workflow_dispatch` itself is the human
  gate). The Tauri updater plugin, previously unregistered because its only
  configured feed was upstream Meetily's GitHub releases, now points at this
  feed; several dead/duplicate update-check code paths in the frontend were
  also fixed. Builds stay ad-hoc signed, unnotarized (no Apple Developer
  account) — accepted tradeoff is that macOS TCC will likely revoke and
  re-prompt for microphone/screen-recording access after most updates, since
  ad-hoc signing has no stable Team Identifier for TCC to key the grant on;
  Gatekeeper's quarantine prompt is unaffected either way, since the updater
  never downloads through a quarantine-setting API. macOS aarch64 only in
  this pass. See `docs/dev/SCRIBE_UPDATE_FEED.md`.

### Fixed

- `meetings` module: avoided a `MissingGreenlet` error by no longer
  re-reading a column that was just assigned via `func.now()` on an ORM
  instance under `AsyncSession` — assigning a server-side SQL expression
  leaves the attribute "expired" post-flush, and a later read
  (`to_meeting_record`) triggered an implicit async refresh that isn't
  safe there.
- `meetings` module: the desktop push's session is now committed before
  scheduling the summarization `BackgroundTask`, not after — this FastAPI
  version runs `BackgroundTasks` before a yield-dependency's own
  post-commit cleanup, so the background task's independent session
  couldn't see the just-created row yet, and every push was failing
  summarization with "meeting not found".
- WusoolScribe desktop app: release workflow's `pnpm` pinned to v10 to
  match the lockfile, and the updater tarball filename corrected — both
  were silently breaking `scribe-release.yml`'s ability to produce a
  working auto-update artifact.
- WusoolScribe desktop app: the main window now explicitly focuses on
  relaunch after an update — a relaunch via the updater spawns the new
  process without the Launch Services activation a normal double-click
  gets, so it was silently landing in the background with no way to
  bring it forward. The update toast was restyled onto sonner's native
  title/description/action API (fixing a doubled icon and cramped
  layout), and `scribe-release.yml` gained a `release_notes` input wired
  into both the GitHub release body and `latest.json`'s `notes` field —
  previously nothing set that field, so the in-app changelog dialog
  always showed an empty body.
- WusoolScribe desktop app: the sidebar footer's version was a hardcoded
  `"v0.4.0"` literal, never updated across three released versions —
  now reads the real `getVersion()`, matching how the About dialog
  already did it. Removed stale "delivered to Slack" copy from the push
  destination description (the meetings-module rewrite above already
  dropped Slack delivery from this pipeline). Fixed the recording-controls
  button and processing/saving overlays flashing right-of-center for one
  frame when navigating back to Home — both used a JS-computed
  `marginLeft` guess to fake centering against the sidebar's width
  instead of `position: absolute` inside the content row that already
  excludes it.

## 2026-09-04

### Fixed

- `sector_focus` and `target_geography` are multi-select enums in Attio but
  were rendered as free-text comma-separated boxes in the `/add-*` and
  `/edit-*` Slack forms. A typo ("Fin tech" for "Fintech") only surfaced as
  an `OptionNotFoundError` after `ack()`, by which point the modal had closed
  and everything else the operator had entered was discarded. Both now carry
  their option lists like every other select field and render as real
  multi-selects, so the invalid value can no longer be entered. Both are also
  covered by the live Attio drift check now, and the Slack view-limit test
  covers the four add/edit form builders (`sector_focus` sits at 85 of
  Slack's 100-option cap, previously unguarded).

## 2026-09-03

### Fixed

- Duplicate active buyer/seller role rows on concurrent `/add-buyer` /
  `/add-seller` for the same organization. Migration `b8f4c1e93a56` moved
  `UNIQUE` from `org_attio_id` to `legacy_entry_id` on the role tables, which
  left the create path's "does this org already have an active role" check
  unbacked by any constraint — two submissions could both pass it before
  either committed. `CreateBuyerUseCase`/`CreateSellerUseCase` now take a
  `SELECT ... FOR UPDATE` row lock on the parent organization
  (`OrganizationRepository.lock`) before that check, serializing same-org
  submissions.

### Changed

- Repo restructured into one `server/` modular-monolith project (#91):
  `terraform/` → `infrastructure/terraform/`,
  `workflows/{n8n,crm-sync,bedrock-ai}/` → `infrastructure/`, and
  `workflows/wusool-toolkit/` + `database/` merged into `server/` (no uv
  workspace, no path dependencies). Per-module and cross-module architecture
  fitness tests now enforce the layering rules. CI/CD path filters, Docker
  build context, and the migration path were repointed accordingly.

## 2026-09-02

### Fixed

- Nightly Attio → PostgreSQL resync hardened: SSM-online preflight,
  CloudWatch log streaming, a 20-minute execution deadline with timed-out
  command cancellation, and a memory/CPU-bounded singleton remote run so a
  runaway resync can't take the toolkit host offline.

### Removed

- Automatic `prod` → `dev` back-merge workflow.

## 2026-08-31

### Added

- `prod-postgres-sync` batch scripts for bulk SOURCE → prod data sync (#81).
- `seller_roles` lead-magnet fields exposed to the bot (#71).

### Fixed

- `/find-match` workflow correctness hardening (#85).
- Firecrawl web fallback restricted to Google Maps leads; Firecrawl markdown
  headings normalized (#84).
- SOURCE Attio field-slug mismatches for organization / person / seller role
  and deal name/stage/owner (#71, #78, #79); Attio-write registries corrected.

## 2026-08-30

### Changed

- `people` table renamed to `person` for singular-noun consistency (#73),
  with follow-up fixes to live webhook / nightly-resync SQL (#74).

## 2026-08-29

### Added

- SOURCE-Attio notes pipeline (#68).

### Changed

- Nightly Attio full-resync rewritten — removed N+1 queries, batched writes,
  added end-of-run consistency verification (#67).

### Fixed

- `/add-*` / `/edit-*` field mapping aligned with the current Postgres schema
  (#70).

## 2026-08-26

### Changed

- Buyer / seller / deal currency converted from AED to USD; seller
  lead-magnet fields added.

### Fixed

- Person soft-deleted on Attio `record.deleted` (#65).

## 2026-08-18

### Added

- Alembic + SQLAlchemy migrations established as the schema source of truth,
  applied in CD via SSM against each environment's RDS; a CI `alembic-check`
  job catches model/migration drift on every PR (#45).
- Real-time Attio → PostgreSQL sync via `POST /webhooks/attio` (upserts
  within ~1 second of an Attio change), plus a nightly automated full resync
  and automatic webhook pause/resume around bulk migrations (#47, #49, #50).

## 2026-08-16

### Added

- Continuous deployment: merging to `dev` / `prod` applies the changed
  OpenTofu stacks in dependency order (`base` → `n8n` / `toolkit` →
  `postgres`) and health-checks n8n and the toolkit bot before declaring
  success. Authentication is GitHub OIDC role assumption — no static AWS keys.
- `prod` as a real deployed environment: its own VPC, n8n instance, and RDS
  instance seeded from a dev snapshot (credentials rotated afterward).

### Changed

- Two hand-maintained Terraform environment directories consolidated into
  per-service stacks parameterized by `envs/{dev,prod}.tfvars`.
- Standardized on OpenTofu, version-pinned via
  `infrastructure/terraform/.opentofu-version`.

## 2026-08 (earlier)

### Added

- AWS Bedrock model access provisioned via Terraform for the matching
  engine — Claude Haiku 4.5, Claude Sonnet 4.6, and Qwen3-235B in
  `eu-central-1`.
- n8n password-reset / invite email on dev and prod, via AWS SES
  (`eu-central-1`, sandbox mode).
- Scribe integration groundwork: the `meetings` table, a least-privilege
  `scribe_pub` role on `wusool_crm`, and dev ↔ prod VPC peering so scribe
  can reach `wusool-prod-postgres`.
