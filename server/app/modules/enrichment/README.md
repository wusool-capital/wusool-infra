# enrichment

Fills missing buyer/seller fields from public sources, and hands the
proposal off for review in the *real* `/edit-seller`/`/edit-buyer` modal —
reusable across buyer and seller; only the field set
(`domain/field_plans.py`) and which edit form gets opened differ.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Structure

```
domain/            # EnrichmentTarget, ProposedFieldValue/EnrichmentProposal, field plans, employee_bands
application/        # EnrichMixin (structured lookup + research+extract), ReviewMixin (hand-off), ports/
providers/          # diffbot/ + people_data_labs/ (structured) — apify/ (LinkedIn company page + profiles/posts) — Firecrawl + Bedrock (fallback)
persistence/        # SqlAlchemyRoleReader — reads current values, resolves a target by role id, loads the company page (and, unwired, a role's contacts); linkedin_history
api/                # /enrich-seller, /enrich-buyer Slack commands + handlers, buyer org → vertical modals, "Review & Save" button
```

### Seller research waterfall

For a seller target, `EnrichMixin.propose` tries three tiers in order, each
only for whatever the previous tier didn't resolve:

1. **Diffbot** (`providers/diffbot/`) — structured firmographics (revenue,
   employee count, location count, founding date, description, HQ,
   LinkedIn, logo, AngelList/Facebook/Twitter). Free tier: 10,000
   credits/month.
2. **People Data Labs** (`providers/people_data_labs/`) — same shape,
   second opinion for whatever Diffbot missed. Free tier: 100 lookups/month
   — thinner, so it's tried second, not called for anything Diffbot already
   resolved.
3. **LinkedIn company page** (`providers/apify/company.py`) — description,
   HQ country, employee range and founding date (the year, stored as 1
   January), from the company's own LinkedIn page. The logo is skipped: it is
   a signed LinkedIn URL that expires within weeks.
   Only runs when the organization already has a `linkedin` URL and fields are
   still missing, because every Apify run is billed. Never part of
   `propose_basic`.
4. **Firecrawl + Bedrock** (existing) — free-text search, LLM-extracted.
   Last resort, and the only tier buyer targets ever use — see below.

A field is only ever asked of one source: the waterfall order above, and
whichever tier resolves a field first is final — later tiers are simply
never asked about it (see `EnrichMixin._structured_lookup`'s `remaining`
tracking and `propose`'s `still_missing`). There is no cross-source
confidence comparison; this optimizes for skipping moot calls, not for
picking the best of several answers.

Each structured provider also returns the homepage of the company it
matched (`CompanyDataResult.website`). `propose_basic` reports it per
contributing provider as `ProviderEvidence`, so `discovery` can check it
against Google Maps before writing; `propose` ignores it.

The structured tiers are optional (`DIFFBOT_API_KEY`/
`PEOPLE_DATA_LABS_API_KEY`/`APIFY_API_TOKEN` unset just skips that tier). For
a buyer target they are asked only about `ORGANIZATION` fields: none of
`BUYER_ROLE_ENRICHABLE_FIELDS` (AUM, investment strategy, notable
investments) are fields any provider's schema tracks — see
`EnrichMixin._structured_lookup`'s docstring.

Diffbot's response shape has been verified against a live account (see
`providers/diffbot/schemas.py`'s docstring for what didn't match the
published docs). People Data Labs has not — confirm its `schemas.py`
against a real `PEOPLE_DATA_LABS_API_KEY` account before relying on it.

### LinkedIn scan (the company page's posts)

After the proposal is posted, `api/dependencies.py::propose_and_post` runs
`LinkedInMixin.scan_linkedin` and replies in the proposal's thread with the
result — the scrape never holds up the proposal, and a failure only logs.

Only the **organization** is scraped. The role's people are not: no profile
scrape, no job changes, no contacts' posts, and contacts are not even read
from the database. The people path is built and tested, but off — see
"People path" below.

- **Company page** (`SqlAlchemyRoleReader.load_linkedin_targets(...,
  include_contacts=False)`): the organization's saved `linkedin` URL. Without
  one the scan is skipped and logged, never searched by name.
- **Apify** (`providers/apify/`): one posts run per scan, capped at 40s with
  Apify's own `timeout` below ours so the vendor stops billing when we stop
  waiting. At most 10 posts, last month only. Any error, timeout or malformed
  item yields an empty result. A company page's "posts" are its reposts, so the
  author is the original poster.
- **Cost log:** every run logs `apify_run actor=… items=… duration_ms=…
  outcome=…`; the token only ever travels in the `Authorization` header.
- **History** (`persistence/linkedin_history.py`, behind
  `LinkedInHistoryPort`): one transaction per scan writes a `tool_runs` row
  (`tool='linkedin_scan'`, the run ledger), one `signals` row per *new* post or
  job change (`source='linkedin'`, typed payload, linked to the run; job
  changes only come from the people path), and one
  `linkedin.scan_completed` `activities` row when something was new, linked to
  the run (`ledger_type='tool_run'`). A signal is new if its (`source`,
  `external_id`) is not stored yet: the post id, or `job_change:{person}:{hash
  of the new title and company}`. `scan_linkedin` returns only the new items, so
  a re-run is quiet, and falls back to the full scan if the history write fails.
  Names, titles and post text live only in `signals`; the append-only
  `activities` row holds counts. The post key is global, so a post stored for
  one organization is not stored again for another. History is committed
  before the Slack reply, so a failed reply leaves those items stored but unshown.

`scan_linkedin_for_role(kind, role_id)` (public) runs the same org-only scan on
its own, for a caller that wants the data without a proposal.

**People path (built, not wired).** `scan_linkedin(target, include_people=True)`
also scrapes a role's contacts: a buyer's `key_contact`, or a seller
organization's people (capped at 3, those with a `person.linkedin` first). It
runs one batched profile scrape plus the contacts' own posts, and reports job
changes (`domain/linkedin.py::detect_job_change`: the scraped title and employer
against `person.job_title` and the organization name, case, punctuation and
containment ignored; a missing CRM value is "unknown", not a change;
`person.role` is not compared). A contact without a URL is skipped, never
searched by name, and listed in the reply. Nothing sets `include_people` today.
Its parsing of the profile scraper has never been run live.

The company and posts schemas were verified against a live run (2026-10-19).
The profile scraper has not been run yet. A company page's "posts" are its
reposts of other people's posts: the author is the original poster, and
`repostedBy` is the company.

### Basic tier

`propose(target, research=False)` skips the Firecrawl + Bedrock tier and asks
only the structured providers. `propose_basic` (exported as
`propose_basic_seller_fields`) does the same for a company that has no saved
role yet, using the caller's draft values as the current ones; `discovery`'s
seller writer uses it before creating a lead. The full tier then runs when a
discovered seller is approved: `matching_engine` calls `enrich_and_post`, which
posts a proposal for review and writes nothing. Providers also receive the
company's domain when known, so a name shared by several companies still
resolves to the right one.

`fetch_json` (and `post_json_array`, used by Apify) logs a 429 as `*_rate_limited` rather than treating it like "no
data", and retries once when `Retry-After` is at most 2 seconds.

## Public contract

`EnrichmentReviewPort`, `RoleReaderPort`, `EnrichmentTarget`,
`EnrichmentTargetKind`, `ProposedFieldValue`, `EnrichmentProposal`,
`WriteTarget`, `enrich_and_post`, `propose_basic_seller_fields`,
`scan_linkedin_for_role` and its result types (`LinkedInScan`, `JobChange`,
`LinkedInPost`, `LinkedInProfile`, `Contact`) — see `__init__.py`.

This module never writes to Attio and never renders a Slack edit form. Its only
Postgres writes are the LinkedIn history rows above (`tool_runs`, `signals`,
`activities`); CRM fields are written by `ddl_commands`. `ddl_commands` implements `EnrichmentReviewPort`
(`providers/enrichment/review_adapter.py`) by opening its own real
`/edit-seller`/`/edit-buyer` modal, prefilled with the proposed values —
the submission then goes through that module's ordinary edit path
unchanged. `server/main.py` wires the two together at startup via
`api.dependencies.configure_review_port` — the dependency edge points
`ddl_commands -> enrichment`, never the reverse.

`enrich_and_post(kind, role_id, channel_id)` is the one entry point another
module needs — it resolves the org itself (`persistence/role_lookup.py`
::`resolve_target`), so a caller (a Slack button on a match result, the
buyer "enrich first?" checkbox) never needs to look up org info on its own.

## Database

Reads `seller_roles`/`buyer_roles`/`organizations`/`person` directly via
`app.models`. Writes `tool_runs`, `signals` and `activities` for the LinkedIn
scan; the `signals.org_attio_id` rename (was `buyer_attio_id`) is the only
migration this module needed.

## Setup

See `server/.env.example`'s `enrichment` section. `FIRECRAWL_API_KEY`,
`DIFFBOT_API_KEY`, `PEOPLE_DATA_LABS_API_KEY`, and `APIFY_API_TOKEN` are all
optional — missing any of them just skips that tier rather than requiring it
to boot. Set a monthly spend cap in Apify. The free plan limits the profile
scraper to 50 runs in total, but only the unwired people path uses it.

## Testing

`uv run pytest app/modules/enrichment/tests` — no real database/AWS/Firecrawl
credentials required; `tests/fakes/` stands in for all three.

## Where to go next

`/enrich-seller <name>` / `/enrich-buyer <name>` (always kind-scoped — no
bare `/enrich`, so an org with both an active buyer and seller role never
needs a role-selection modal just to pick the kind; or a match result's
"Enrich" button; `/enrich-buyer` instead goes organization → vertical via
`api/slack/views/buyer_selection.py`, like `/edit-buyer`; a single-role org
skips the vertical step)
→ `enrich_and_post` → `api/dependencies.py
::propose_and_post` (background task, mirrors
`matching_engine.run_match_and_post`) → `EnrichMixin.propose` →
`api/slack/views/proposal_message.py` (shows every proposed field, one
"Review & Save" button) → operator clicks it → `handlers/actions.py` →
`ReviewMixin.open_review_form` (carries a `card_token` from `discovery.store_review_card`; the
edit-form save swaps the button for "✅ ADDED by") → `EnrichmentReviewPort` → `ddl_commands`'
real, prefilled edit modal → the ordinary edit-form write path.
