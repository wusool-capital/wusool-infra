-- Marks voices the voice library named on its own, so the app can ask the user
-- to confirm them. Naming a voice by hand clears it. Existing rows predate
-- auto-naming tracking, so they stay unmarked.
ALTER TABLE meeting_speakers ADD COLUMN auto_named INTEGER NOT NULL DEFAULT 0;
