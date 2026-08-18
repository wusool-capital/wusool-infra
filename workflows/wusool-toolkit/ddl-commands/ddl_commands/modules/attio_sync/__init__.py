"""Real-time DEV Attio -> Postgres sync, driven by Attio's own webhooks.

`POST /webhooks/attio` (see `router.py`) is the entrypoint: Attio calls it the
instant any object record or list entry changes in DEV Attio, for any reason
(a human editing the Attio UI, `/add-seller`/`/edit-seller` writing through
this same bot, or any other integration). The webhook payload only ever
carries IDs, never values (`dispatch.py`), so every event re-fetches that one
record's current state and upserts it (`upsert.py`) — the same field mapping
and `ON CONFLICT` SQL already proven in `database/sync-postgres.ps1`, scoped
to a single row instead of a full page-through.

This complements, not replaces, `sync-postgres.ps1`'s periodic full resync —
that script remains the safety net for anything a missed webhook delivery or
an out-of-order race leaves inconsistent (see `upsert.py`'s module docstring
for the specific races this accepts rather than closes).
"""
