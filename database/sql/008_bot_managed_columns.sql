-- Soft-delete + sync-collision-guard columns for the ddl-commands Slack
-- bot's write commands (/edit-seller, /remove-seller, /edit-buyer,
-- /remove-buyer). Additive only.
--
-- bot_managed_by is last-writer-wins (the Slack user ID of whoever most
-- recently created/updated/archived/restored this row) — a "who do I ask
-- about this row right now" pointer, NOT a history of every actor who has
-- ever touched it. If that distinction matters later, it needs a separate
-- audit table, not a wider read of this column.

ALTER TABLE seller_roles ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE seller_roles ADD COLUMN IF NOT EXISTS bot_managed_at timestamptz;
ALTER TABLE seller_roles ADD COLUMN IF NOT EXISTS bot_managed_by text;

ALTER TABLE buyer_roles ADD COLUMN IF NOT EXISTS archived_at timestamptz;
ALTER TABLE buyer_roles ADD COLUMN IF NOT EXISTS bot_managed_at timestamptz;
ALTER TABLE buyer_roles ADD COLUMN IF NOT EXISTS bot_managed_by text;
