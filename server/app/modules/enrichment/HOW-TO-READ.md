# How to read this module

Follow one `/enrich-seller <name>` request end to end (`/enrich-buyer` is the
same path, kind-scoped the other way; a match result's "Enrich" button and
the seller-add "Enrich" button both land on the same `enrich_and_post`
entry point, just with the org already known/resolved rather than searched
by name).

1. `api/slack/handlers/commands.py::_handle_enrich_command` — resolves org+role
   candidates via `api/dependencies.py::resolve_org_roles` (organizations trigram search).
2. One match → straight to step 4. Multiple → `api/slack/views/role_selection.py` modal,
   submission handled in `handlers/actions.py`.
3. `api/dependencies.py::propose_and_post` — posts a placeholder, since research + LLM
   extraction routinely runs past Slack's 3s ack budget (same pattern as
   `matching_engine.run_match_and_post`).
4. `application/enrich.py::EnrichMixin.propose` — reads current values
   (`persistence/role_lookup.py`), researches gaps (`providers/firecrawl/client.py`),
   extracts candidate values (`providers/bedrock/client.py`), drops anything below
   `ENRICHMENT_MIN_CONFIDENCE`.
5. `api/slack/views/proposal_message.py` — renders every proposed field for review, with
   one "Review & Save" button (not per-field buttons — the whole point is to open the
   real edit form, not build a second write UI).
6. Operator clicks it → `handlers/actions.py::handle_review` → `decode_proposal` resolves
   the button's opaque token via `utilities`' shared, in-memory, TTL-evicted
   `EphemeralStore` (`get_shared_ephemeral_store`) — the full proposal JSON no longer
   fits directly in the button's own `value`, which Slack caps at 2000 characters; a
   well-documented org now routinely proposes enough fields to exceed that on its own
   (`ddl_commands`' organization-selection modal and `discovery`'s lead-add button use
   the same store for the same reason) → `application/review.py
   ::ReviewMixin.open_review_form` → `EnrichmentReviewPort`. An expired/unknown token
   (store TTL passed, or the process restarted) surfaces a "run `/enrich-seller`/
   `/enrich-buyer` again" message instead of a crash.
7. `ddl_commands/providers/enrichment/review_adapter.py` implements that Port — resolves
   the real role+org, splits the proposed values into org-fields vs. role-fields, and
   opens `seller_form.py`/`buyer_form.py`'s real edit modal with `prefill` set to the
   proposed values (winning over the row's current ones — that's the point of a review).
   `server/main.py` wires this adapter in at startup.
8. The operator reviews/edits in that real form and submits — the write itself is the
   *existing* `seller_edit_form_modal`/`buyer_edit_form_modal` submission handler
   (`ddl_commands/api/slack/handlers/actions.py`), completely unchanged. `enrichment`
   never writes anything itself.

## Why a single button instead of per-field ones

The first version of this module posted one "Accept & Save" button per proposed field,
each writing that field immediately and independently, since research runs in the
background and a `views_open` modal needs a `trigger_id` that background task no longer
has. That's still true — but the *button click itself* has a fresh `trigger_id`, so
instead of building a second, bespoke write path, the click opens the same real edit form
an operator would use anyway, prefilled. One review, one form, one write path — reusing
`ddl_commands`'s existing modal instead of enrichment inventing its own.
