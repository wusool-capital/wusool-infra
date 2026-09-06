-- Migration: Add buyer/seller push tag to meetings
-- Distinct from folder_path (the local filesystem folder holding the
-- recording's audio files) -- this stores the business-facing grouping
-- tag (e.g. "Buyer - Acme Corp") the user assigns before pushing a
-- meeting to the Scribe backend. NULL until the user tags a meeting.

ALTER TABLE meetings ADD COLUMN push_tag TEXT;
