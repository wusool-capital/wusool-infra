# discovery

Finds sellers outside the CRM via public search (moved from
`matching_engine`'s old Google-Maps-only web fallback), checks each against
the CRM, and auto-creates the ones that are new. A lead that only looks like
an existing organization is handed to `ddl_commands`' `/add-seller` form,
prefilled, for a human to decide.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/internal/dev/MODULAR_MONOLITH_GUIDE.md)._

## Structure

```
domain/            # DiscoveredLead, SellerDraft, CrmMatch, DiscoveryOutcome
application/        # DiscoverMixin, CreateMixin (pre-filter + create), ConfirmMixin, ports/
providers/          # Google Places client (replaced the Firecrawl Maps scraper)
api/                # discover_and_create_sellers (called by matching_engine), discover_add_seller handler
```

No `persistence/` layer, and no database connection at all — the CRM is
reached only through `SellerWriterPort`.

## Public contract

`discover_and_create_sellers`, `DiscoveryOutcome`, `SellerWriterPort`,
`SellerDraftPort` and their value types — see `__init__.py`. This module never
creates a `seller_roles`/`organizations` row itself. `ddl_commands` implements
both ports: `SellerWriterPort` (`providers/discovery/seller_writer_adapter.py`)
looks a lead up and creates it headlessly, and `SellerDraftPort`
(`providers/discovery/seller_draft_adapter.py`) opens the real, prefilled
`/add-seller` modal. `server/main.py` wires them at startup, the same pattern
`enrichment` uses for its own `EnrichmentReviewPort`.

## The CRM pre-filter

Auto-creating leads removes the human `/add-seller` step, which used to be
the only dedupe in the pipeline, so the check now runs in code, before any
write (`CreateMixin.discover_and_create`):

- **Exact `place_id` or domain match** (`CrmMatchKind.PLACE_ID`/`DOMAIN`):
  skipped and counted as "already in the CRM". Exact identifiers are safe to
  act on unattended.
- **Name-only match** (`FUZZY_NAME`, `organizations.org_name_trigram_predicate`,
  threshold 0.3): *not* created. That threshold is tuned for an advisor
  reviewing every hit, so it comes back as a `PossibleDuplicate`, posted with
  an "Add as seller" button. The `/add-seller` organization search is the
  human's final check.
- **No match**: enriched (basic tier) and created in one Attio-first write.

Places returns up to 20 results for the price of one, so the search asks for
all of them and the pre-filter picks the first `DISCOVERY_LEAD_SEARCH_LIMIT`
survivors; skipped leads free their slots for the next results. Google has no
"exclude these places" filter, so this is the only place they can be dropped.

A per-day search cap per buyer role (`DISCOVERY_DAILY_SEARCH_CAP`) guards
against a runaway loop. It is in-process: it resets on deploy and isn't shared
across instances.

## Setup

See `server/.env.example`'s `discovery` section. `GOOGLE_PLACES_API_KEY`
covers both Places Text Search and the Geocoding API (billed to the same
Google Cloud project/key) — optional; lead search is disabled without it.

## Testing

`uv run pytest app/modules/discovery/tests` — no real Slack/Google Places
credentials required; `tests/fakes/` stands in for both.

## Where to go next

Automatic: `matching_engine.api.dependencies.trigger_seller_discovery` (below
a score threshold) → `discover_and_create_sellers`. Manual: the "Find more
sellers" button on the match-result message → same function. Then:
`CreateMixin.discover_and_create` → `SellerWriterPort.find_existing` per lead
→ `SellerWriterPort.enrich_and_create` for new ones → a typed
`DiscoveryOutcome` back to `matching_engine`, which appends the created
sellers to the run as `PENDING_REVIEW` rows (Approve opens a Qualified deal and
posts the full enrichment proposal)
and posts the possible duplicates. Their "Add as seller" button →
`api/slack/handlers.py` → `domain/drafts.py::draft_from_lead` →
`ConfirmMixin.open_confirm_form` → `SellerDraftPort` → `ddl_commands`'
prefilled `/add-seller` modal.
