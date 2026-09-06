# How to read `ddl_commands`

A walkthrough for someone who has never seen this module before. See
`README.md` first — it already documents *what* the edit/add flows do and
*why* they're Attio-first; this file is about *where the code for each
step lives*, so you can jump straight to it.

## The one-sentence version

Four Slack commands (`/edit-seller`, `/edit-buyer`, `/add-seller`,
`/add-buyer`) that write to DEV Attio first, then Postgres — plus a
completely separate, always-running path that keeps Postgres in sync with
Attio via webhooks. These two paths share tables but almost nothing else;
treat them as two different modules that happen to live in one folder.

## Path 1: a Slack command, end to end

Follow `/edit-seller <name>` through the code — the add flow is the same
shape with an extra org-selection step (see `README.md`'s "The add flow").

```
1. User types /edit-seller in Slack
   -> api/slack/handlers/commands.py
      - acks fast, resolves the name to 0/1/many sellers
        (via application/sellers.py's SellerService.resolve_seller)
      - opens the first modal

2. Disambiguation modal (if >1 match)
   -> api/slack/views/seller_role_selection.py

3. Field picker modal — "which fields do you want to edit?"
   -> api/slack/views/field_picker.py
      (the eligibility list — which fields are even offered — lives in
      api/sellers.py's SELLER_ROLE_FIELDS / GATED_SELLER_ROLE_FIELDS,
      not hardcoded in the modal-building code)

4. Edit form modal — only the picked fields, pre-filled
   -> api/slack/views/seller_form.py
      (dynamic per-field widgets: api/slack/views/dynamic_fields.py)

5. Submit -> api/slack/handlers/actions.py (_write_seller_edit)
   - re-resolves the target row fresh (never trusts what the payload
     claims the current values are)
   - converts the submitted values into Attio's write shape
     -> providers/attio/write_payload.py
   - writes DEV Attio FIRST (via app.modules.attio's client + entries.py)
   - only then writes Postgres
     -> application/sellers.py (SellerService) -> persistence/repositories/
        sellers_repository.py, inside a Unit-of-Work
        (persistence/unit_of_work.py)
   - if Attio succeeded but Postgres then failed (or vice versa for the
     add flow's two-step org-then-role write), the ephemeral Slack message
     says exactly what already landed — see PartialWriteError in
     actions.py
```

`api/slack/handlers/actions.py` is the single biggest file in this module
(~960 lines) because it holds all four submit handlers
(`_write_seller_edit`, `_write_buyer_edit`, `_write_seller_add`,
`_write_buyer_add`) plus every modal-to-modal transition in between. If
you're debugging a specific submit path, jump straight to that function —
you don't need to read the whole file.

## Path 2: the Attio webhook sync (completely separate)

This path has nothing to do with Slack. Attio calls *this app* whenever a
record changes (in DEV Attio, or via the nightly full-resync script), and
this path writes that change into `wusool_crm`.

```
1. Attio POSTs to /webhooks/attio
   -> api/attio_sync.py
      - verifies the HMAC signature FIRST — before anything else runs
      - acks immediately, does the real work in a FastAPI BackgroundTask
        (Attio never waits on this; a slow/failed sync never blocks the
        Slack bot sharing this same process)

2. -> application/attio_sync.py (dispatch_event)
      - a stateless per-event dispatcher, not a class with injected
        dependencies (see application/service.py's docstring for why it's
        deliberately kept outside the DdlCommandsService facade)
      - Attio's webhook payload carries only IDs, never values, so this
        always re-fetches the current record from Attio before writing
        anything to Postgres

3. -> persistence/attio_sync.py (the big one, ~1150 lines)
      - one pure "params mapper" function per table (no I/O — just
        Attio's fetched JSON -> a dict of Postgres column values) and one
        thin "fetch + upsert" wrapper per table that calls it
      - every upsert is idempotent — safe to run for the same event twice,
        in any order

scripts/attio_sync_full_resync.py is the batch-job version of the same
idea: it calls persistence/attio_sync.py's mapper functions directly
against its own paged-through bulk fetch, instead of going through the
webhook wrapper. Run this after a schema change or if the sync ever drifts.
```

Why this exists as a safety net at all: `README.md`'s "Why Attio-first"
section explains that Postgres treats Attio as the source of truth, and a
scheduled `sync-postgres.ps1` script already converges Postgres to match
it — this webhook path is what keeps that convergence near-real-time
instead of waiting for the next nightly run.

## Layering notes specific to this module

- **No `domain/` layer.** Every other file in `application/`/`persistence/`
  works with `app.models` ORM rows directly (see `application/buyers.py`'s
  `BuyerResolution` docstring for the explicit reasoning) — there was
  never enough framework-free business logic here to justify a separate
  layer. Don't add one "for consistency" without a real reason.
- **`application/service.py`** composes `BuyerService`/`SellerService`
  into one `DdlCommandsService` facade, same mixin pattern as
  `matching_engine`/`meetings`. `application/attio_sync.py`'s
  `dispatch_event` deliberately sits **outside** that facade — it's a
  stateless per-webhook-event function, not a service with dependencies
  wired in once.
- **`api/schemas.py`** defines `FieldSpec`/`FieldKind` — the single
  source of truth for which fields exist and how to render/validate them.
  If you're adding a new editable field, this is almost always the first
  file to touch, followed by `api/sellers.py`/`api/buyers.py`/
  `api/organizations.py`'s field lists.

## Where to go next

- Adding or changing an editable field → `api/schemas.py` (`FieldSpec`),
  then `api/{sellers,buyers,organizations}.py`'s field lists, then
  `providers/attio/write_payload.py` if it needs special Attio-shape
  handling.
- Debugging a specific Slack submit → jump straight to its function in
  `api/slack/handlers/actions.py`.
- Working on the Attio-to-Postgres sync → `persistence/attio_sync.py`
  (the actual upserts), `application/attio_sync.py` (routing), or
  `scripts/attio_sync_full_resync.py` (the batch equivalent).
- The concurrency/locking subtlety around two people editing the same org
  at once → `README.md`'s "Known limitation" section, already documents
  this in full; don't re-derive it from the code.
