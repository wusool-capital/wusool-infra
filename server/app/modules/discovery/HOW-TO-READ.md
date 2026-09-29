# How to read this module

Follow the "find more sellers" flow end to end.

1. Trigger: `matching_engine`'s below-threshold auto-check
   (`api/dependencies.py::trigger_seller_discovery`), or the "Find more sellers" button on
   any match-result message (`handlers/actions.py::handle_discover_more_sellers`). Either
   way it lands on this module's `discover_and_create_sellers` (its one public entry point).
2. `api/lead_flow.py::discover_and_create_sellers` →
   `application/create.py::CreateMixin.discover_and_create`: checks the per-day cap, then
   `providers/google_places/client.py::GooglePlacesClient` (Google Places API Text
   Search, geocoded and country-restricted to `geography`) returns up to 20 leads.
3. Each lead goes through `SellerWriterPort.find_existing` — the CRM pre-filter. An exact
   `place_id`/domain match is skipped; a name-only match becomes a `PossibleDuplicate`;
   anything else is created via `SellerWriterPort.enrich_and_create` (2 at a time, within
   an overall time budget). The result is a typed `DiscoveryOutcome`.
4. `ddl_commands/providers/discovery/seller_writer_adapter.py` implements that Port: basic
   enrichment in memory, then one Attio-first write through
   `ddl_commands/api/seller_write.py::write_seller_add`. `server/main.py` wires it at
   startup.
5. `matching_engine` appends the created sellers to the run as `PENDING_REVIEW` rows
   (Approve opens a Qualified deal, Reject just updates the status) and posts them. Possible
   duplicates are posted by `api/slack/views.py::build_possible_duplicate_blocks`, one "Add
   as seller" button per lead, the lead stored server-side and an opaque token encoded in the
   button value (`api/dependencies.py::encode_lead`/`decode_lead`, via `utilities`' shared
   ephemeral store — same reason `enrichment`'s proposal button does this).
6. Operator clicks a possible duplicate → `api/slack/handlers.py::handle_discover_add_seller`
   → `domain/drafts.py::draft_from_lead` (pure mapping — a Places category becomes a
   `sector_focus` guess, a Places country becomes an `hq_country` prefill; a street
   address maps to nothing, since there's no organization field for it) →
   `application/confirm.py::ConfirmMixin.open_confirm_form` → `SellerDraftPort`.
7. `ddl_commands/providers/discovery/seller_draft_adapter.py` implements that Port — it
   runs the same org search `/add-seller` always runs and opens either
   `organization_selection_modal` or the real `/add-seller` modal, prefilled with the
   draft's values, so a human makes the final duplicate call.

See the README's "The CRM pre-filter" for why exact and fuzzy matches are treated
differently.
