# enrichment

Fills missing buyer/seller fields from public sources, and hands the
proposal off for review in the *real* `/edit-seller`/`/edit-buyer` modal —
reusable across buyer and seller; only the field set
(`domain/field_plans.py`) and which edit form gets opened differ.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

## Structure

```
domain/            # EnrichmentTarget, ProposedFieldValue/EnrichmentProposal, field plans, employee_bands
application/        # EnrichMixin (structured lookup + research+extract), ReviewMixin (hand-off), ports/
providers/          # diffbot/ + people_data_labs/ (structured, seller-only) — Firecrawl + Bedrock (fallback)
persistence/        # SqlAlchemyRoleReader — reads current values + resolves a target by role id
api/                # /enrich-seller, /enrich-buyer Slack commands + handlers, "Review & Save" button
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
3. **Firecrawl + Bedrock** (existing) — free-text search, LLM-extracted.
   Last resort, and the only tier buyer targets ever use — see below.

A field is only ever asked of one source: the waterfall order above, and
whichever tier resolves a field first is final — later tiers are simply
never asked about it (see `EnrichMixin._structured_lookup`'s `remaining`
tracking and `propose`'s `still_missing`). There is no cross-source
confidence comparison; this optimizes for skipping moot calls, not for
picking the best of several answers.

Both structured tiers are optional (`DIFFBOT_API_KEY`/
`PEOPLE_DATA_LABS_API_KEY` unset just skips that tier) and are never called
for a buyer target at all: none of `BUYER_ENRICHABLE_FIELDS` (AUM,
investment strategy, notable investments) are fields either provider's
schema tracks, so it would be a guaranteed-empty round trip every time —
see `EnrichMixin._structured_lookup`'s docstring.

Diffbot's response shape has been verified against a live account (see
`providers/diffbot/schemas.py`'s docstring for what didn't match the
published docs). People Data Labs has not — confirm its `schemas.py`
against a real `PEOPLE_DATA_LABS_API_KEY` account before relying on it.

## Public contract

`EnrichmentReviewPort`, `RoleReaderPort`, `EnrichmentTarget`,
`EnrichmentTargetKind`, `ProposedFieldValue`, `EnrichmentProposal`,
`WriteTarget`, `enrich_and_post` — see `__init__.py`.

This module never writes to Attio or Postgres itself, and never renders a
Slack edit form. `ddl_commands` implements `EnrichmentReviewPort`
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

Reads `seller_roles`/`buyer_roles`/`organizations` directly via `app.models`
(no migration — every enrichable field already exists on those tables).

## Setup

See `server/.env.example`'s `enrichment` section. `FIRECRAWL_API_KEY`,
`DIFFBOT_API_KEY`, and `PEOPLE_DATA_LABS_API_KEY` are all optional —
missing any of them just skips that tier rather than requiring it to boot.

## Testing

`uv run pytest app/modules/enrichment/tests` — no real database/AWS/Firecrawl
credentials required; `tests/fakes/` stands in for all three.

## Where to go next

`/enrich-seller <name>` / `/enrich-buyer <name>` (always kind-scoped — no
bare `/enrich`, so an org with both an active buyer and seller role never
needs a role-selection modal just to pick the kind; or a match result's
"Enrich" button) → `enrich_and_post` → `api/dependencies.py
::propose_and_post` (background task, mirrors
`matching_engine.run_match_and_post`) → `EnrichMixin.propose` →
`api/slack/views/proposal_message.py` (shows every proposed field, one
"Review & Save" button) → operator clicks it → `handlers/actions.py` →
`ReviewMixin.open_review_form` → `EnrichmentReviewPort` → `ddl_commands`'
real, prefilled edit modal → the ordinary edit-form write path.
