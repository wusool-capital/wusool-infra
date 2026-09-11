# How to read this module

Follow the "find more sellers" flow end to end.

1. Trigger: `matching_engine`'s below-threshold auto-check
   (`api/dependencies.py::trigger_seller_discovery`), or the "Find more sellers" button on
   any match-result message (`handlers/actions.py::handle_discover_more_sellers`). Either
   way it lands on this module's `find_and_post_leads` (its one public entry point).
2. `api/lead_flow.py::find_and_post_leads` — posts a placeholder, then
   `application/discover.py::DiscoverMixin.find_leads` →
   `providers/firecrawl/client.py::FirecrawlMapsClient` (Google Maps scrape, moved
   verbatim from `matching_engine`'s old web fallback).
3. `api/slack/views.py::build_lead_blocks` — one "Add as seller" button per lead, the
   lead itself encoded in the button value (`api/dependencies.py::encode_lead`) so the
   click needs no server-side lookup.
4. Operator clicks a lead → `api/slack/handlers.py::handle_discover_add_seller` →
   `domain/drafts.py::draft_from_lead` (pure mapping — a scraped category becomes a
   `sector_focus` guess; a street address maps to nothing, since there's no organization
   field for it) → `application/confirm.py::ConfirmMixin.open_confirm_form` →
   `SellerDraftPort`.
5. `ddl_commands/providers/discovery/seller_draft_adapter.py` implements that Port — it
   runs its *own* org search (the same one `/add-seller` always runs) and either opens
   `organization_selection_modal` (an org already fuzzy-matches — that flow's existing
   "already has a seller role, use `/edit-seller` instead" check is the only dedupe this
   pipeline has) or the real `/add-seller` modal, prefilled with the draft's values.
   `server/main.py` wires this adapter in at startup.

There is deliberately no separate dedupe step in this module itself — see the README's
"Why no dedupe here".
