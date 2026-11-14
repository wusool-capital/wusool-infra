-- Set on every local notes edit, cleared once the server has the same text.
ALTER TABLE meeting_notes ADD COLUMN needs_sync INTEGER NOT NULL DEFAULT 0;
