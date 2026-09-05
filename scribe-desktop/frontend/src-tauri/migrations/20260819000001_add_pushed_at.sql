-- Migration: Add pushed_at to meetings
-- Persists whether a meeting has already been pushed to Scribe (set by
-- push_meeting once the backend accepts it), independent of in-session
-- React state -- reopening the app must still know a meeting is locked
-- for editing. NULL until pushed.

ALTER TABLE meetings ADD COLUMN pushed_at TEXT;
