# discovery

Finds sellers outside the CRM via public search (moved from
`matching_engine`'s old Google-Maps-only web fallback), and hands a
discovered lead straight off to `ddl_commands`' `/add-seller` form,
prefilled.

_New to this codebase's layering? See
[the modular monolith guide](../../../../docs/dev/MODULAR_MONOLITH_GUIDE.md)._

## Structure

```
domain/            # DiscoveredLead, SellerDraft, draft_from_lead
application/        # DiscoverMixin (search), ConfirmMixin (hand-off), ports/
providers/          # Firecrawl Google-Maps client (moved from matching_engine)
api/                # find_and_post_leads (called by matching_engine), discover_add_seller handler
```

No `persistence/` layer, and no database connection at all — see "Why no
dedupe here" below.

## Public contract

`DiscoveredLead`, `SellerDraft`, `SellerDraftPort`, `find_and_post_leads` —
see `__init__.py`. This module never creates a `seller_roles`/`organizations`
row itself. `ddl_commands` implements `SellerDraftPort`
(`providers/discovery/seller_draft_adapter.py`) by opening the real,
prefilled `/add-seller` modal — the submission then goes through that
module's ordinary create path unchanged. `server/main.py` wires the two
together at startup, the same pattern `enrichment` uses for its own
`EnrichmentReviewPort`.

## Why no dedupe here

This module used to run its own "does a matching seller already exist?"
check before handing a lead to `ddl_commands`. It didn't need to:
`ddl_commands`' own `/add-seller` flow already does exactly that search
(`search_organizations` → `organization_selection_modal`), and already says
"this org already has a seller role — use `/edit-seller` instead" when one
exists. Running a second, independent dedupe here was pure duplication —
`discover_add_seller` now hands the lead straight to
`SellerDraftPort.open_confirm_form`, and `ddl_commands`' existing search is
the *only* dedupe in this pipeline.

## Setup

See `server/.env.example`'s `discovery` section. `FIRECRAWL_API_KEY` is
shared with `matching_engine`/`enrichment` — optional; lead search is
disabled without it.

## Testing

`uv run pytest app/modules/discovery/tests` — no real Slack/Firecrawl
credentials required; `tests/fakes/` stands in for both.

## Where to go next

Automatic: `matching_engine.api.dependencies.trigger_seller_discovery` (below
a score threshold) → `find_and_post_leads`. Manual: the "Find more sellers"
button on the match-result message → same function. Either way:
`find_and_post_leads` → `DiscoverMixin.find_leads` → message with one
"Add as seller" button per lead → `api/slack/handlers.py` →
`domain/drafts.py::draft_from_lead` → `ConfirmMixin.open_confirm_form` →
`SellerDraftPort` → `ddl_commands`' prefilled `/add-seller` modal, which
runs its own search and either offers "use `/edit-seller` instead" or opens
the prefilled create form.
